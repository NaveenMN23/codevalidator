import json
import re
from infrastructure.logger import log
from infrastructure.storage import storage_client
from config.settings import settings
from services.llm import llm_client
from services.sanitizer import sanitizer
from services.validators import (
    DesignOutput,
    SkeletonOutput,
    FunctionDeltaOutput,
    validate_with_correction,
)
from generator.engine import generator

_SUPPORTED_LANGUAGES = {"node", "java", "python"}
_TIERS = ("easy", "medium", "hard")


def _replace_function_body(content: str, fn_name: str, new_body: str, language: str) -> str:
    """Fallback injection: find fn_name in content and replace its throw/raise with new_body.

    Used when the exact stub marker wasn't found (LLM used a slightly different message).
    For brace-delimited languages (Node/Java): finds function by name, counts braces to
    locate the body, replaces the single throw statement inside.
    For Python: finds the def line and replaces the raise statement in the body.
    """
    if language == "python":
        lines = content.split("\n")
        fn_def_idx = None
        fn_indent = 0
        for i, line in enumerate(lines):
            m = re.match(rf'^(\s*)def\s+{re.escape(fn_name)}\s*\(', line)
            if m:
                fn_def_idx = i
                fn_indent = len(m.group(1))
                break
        if fn_def_idx is None:
            log.warning(f"_replace_function_body: def {fn_name}( not found in Python file")
            return content
        # Walk forward to find the raise/pass in the body
        for i in range(fn_def_idx + 1, len(lines)):
            stripped = lines[i].lstrip()
            if not stripped:
                continue
            line_indent = len(lines[i]) - len(stripped)
            if line_indent <= fn_indent:
                break  # left the function
            if stripped.startswith(("raise ", "pass")):
                lines[i] = " " * line_indent + new_body.strip()
                return "\n".join(lines)
        log.warning(f"_replace_function_body: no raise/pass found in def {fn_name}()")
        return content
    else:
        # Node / Java: brace-counted body replacement
        fn_match = re.search(rf'\b{re.escape(fn_name)}\s*\(', content)
        if not fn_match:
            log.warning(f"_replace_function_body: {fn_name}( not found")
            return content
        brace_start = content.find("{", fn_match.end())
        if brace_start == -1:
            log.warning(f"_replace_function_body: no opening brace after {fn_name}(")
            return content
        depth = 0
        brace_end = -1
        for i in range(brace_start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    brace_end = i
                    break
        if brace_end == -1:
            log.warning(f"_replace_function_body: unmatched braces for {fn_name}")
            return content
        # Preserve body indentation from the original throw line
        original_body = content[brace_start + 1:brace_end]
        indent_match = re.search(r'\n(\s+)', original_body)
        indent = indent_match.group(1) if indent_match else "  "
        return (
            content[:brace_start + 1]
            + "\n" + indent + new_body.strip() + "\n"
            + content[brace_end:]
        )

# Stub throw statement per language — must match what the skeleton prompt generates
_STUB_THROW = {
    "node": "throw new Error('not implemented: {tag}');",
    "java": 'throw new UnsupportedOperationException("not implemented: {tag}");',
    "python": 'raise NotImplementedError("not implemented: {tag}")',
}


class ScaffoldGenerator:
    """Three-phase CoT generator — skeleton + delta architecture.

    Phase 1:  design_challenge         → 3 tiers × N scenarios design document
    Phase 2a: implement_skeleton_{lang} × 3 → full codebase per tier; all N target
              functions are explicit stubs (`throw new Error('not implemented: ...')`).
              Non-target functions are fully implemented as pattern examples.
    Phase 2b: implement_function_{lang} × 3N → implements exactly one stubbed function
              per call and generates its hidden test file.

    Assembly:
      gold master = skeleton with ALL N function bodies injected back (for blueprint + tests)
      student scaffold = skeleton unchanged (stubs as-is) + scenario-specific README

    Phase 3: generate_blueprint × 3N → blueprints stored in Postgres + Redis
    """

    def generate(self, problem_description: str, language: str = "node") -> dict:
        if language not in _SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language {language!r}. Choose from: {_SUPPORTED_LANGUAGES}"
            )

        llm_client.reset_session_cost()
        clean_description = sanitizer.sanitize_description(problem_description)

        # ── Phase 1 — Architecture Design ────────────────────────────────────────
        design_system = llm_client.load_prompt("design_challenge")
        log.info(f"ScaffoldGenerator: Phase 1 (design, language={language})")
        raw_design = llm_client.complete_json(
            design_system,
            f"<language>{language}</language>\n<problem>\n{clean_description}\n</problem>",
            label="design",
        )
        design: DesignOutput = validate_with_correction(
            raw_design,
            DesignOutput,
            llm_client.complete_json,
            design_system,
            f"<language>{language}</language>\n<problem>\n{clean_description}\n</problem>",
            label="design-validate",
        )
        challenge_name = design.challenge.get("name", "challenge")
        log.info(f"ScaffoldGenerator: Phase 1 complete — challenge={challenge_name}")

        # ── Phase 2a — Skeleton per tier (3 calls) ────────────────────────────────
        skeleton_system = llm_client.load_prompt(f"implement_skeleton_{language}")
        tier_skeletons: dict[str, SkeletonOutput] = {}

        for tier in _TIERS:
            tier_design = design.difficulty_tiers[tier]
            scenarios_json = json.dumps(tier_design["scenarios"], indent=2)
            user_context = (
                f"<problem>\n{clean_description}\n</problem>\n\n"
                f"<design>\n{json.dumps(design.model_dump(), indent=2)}\n</design>\n\n"
                f"<tier>{tier.upper()}</tier>\n"
                f"<scenarios>\n{scenarios_json}\n</scenarios>"
            )
            scenario_tags = [s["scenario_tag"] for s in tier_design["scenarios"]]
            log.info(
                f"ScaffoldGenerator: Phase 2a skeleton — tier={tier}, scenarios={scenario_tags}"
            )
            raw_skeleton = llm_client.complete_json_cached(
                skeleton_system,
                user_context,
                label=f"skeleton-{tier}",
                max_tokens_override=settings.openai_max_tokens_impl,
            )
            skeleton: SkeletonOutput = validate_with_correction(
                raw_skeleton,
                SkeletonOutput,
                lambda sys, usr, t=tier: llm_client.complete_json_cached(
                    sys, usr,
                    label=f"skeleton-{t}-retry",
                    max_tokens_override=settings.openai_max_tokens_impl,
                ),
                skeleton_system,
                user_context,
                label=f"skeleton-{tier}-validate",
            )
            tier_skeletons[tier] = skeleton
            log.info(
                f"ScaffoldGenerator: Phase 2a done — tier={tier}, "
                f"files={list(skeleton.files.keys())}"
            )

        # ── Phase 2b — Function deltas per scenario (3×N calls) ──────────────────
        function_system = llm_client.load_prompt(f"implement_function_{language}")
        tier_deltas: dict[str, dict[str, FunctionDeltaOutput]] = {}

        for tier in _TIERS:
            skeleton = tier_skeletons[tier]
            tier_design = design.difficulty_tiers[tier]
            tier_deltas[tier] = {}

            for scenario in tier_design["scenarios"]:
                tag = scenario["scenario_tag"]
                stub_loc = skeleton.stub_locations.get(tag)
                stub_file_content = (
                    skeleton.files.get(stub_loc.file, "") if stub_loc else ""
                )
                user_context = (
                    f"<tier>{tier.upper()}</tier>\n"
                    f"<scenario_tag>{tag}</scenario_tag>\n"
                    f"<scenario_title>{scenario['title']}</scenario_title>\n"
                    f"<scenario_description>{scenario['description']}</scenario_description>\n"
                    f"<strip_description>{scenario.get('strip_description', '')}</strip_description>\n"
                    f"<stub_file>{stub_loc.file if stub_loc else ''}</stub_file>\n"
                    f"<stub_file_content>\n{stub_file_content}\n</stub_file_content>\n"
                    f"<full_skeleton>\n{json.dumps(skeleton.files, indent=2)}\n</full_skeleton>"
                )
                log.info(f"ScaffoldGenerator: Phase 2b delta — scenario={tag}, tier={tier}")
                raw_delta = llm_client.complete_json(
                    function_system,
                    user_context,
                    label=f"function-{tag}",
                    max_tokens_override=settings.openai_max_tokens_test,
                )
                delta: FunctionDeltaOutput = validate_with_correction(
                    raw_delta,
                    FunctionDeltaOutput,
                    llm_client.complete_json,
                    function_system,
                    user_context,
                    label=f"function-{tag}-validate",
                )
                tier_deltas[tier][tag] = delta
                log.info(f"ScaffoldGenerator: Phase 2b done — scenario={tag}")

        # ── Build manifest ────────────────────────────────────────────────────────
        manifest = self._build_manifest(challenge_name, language, design)

        # ── Upload gold masters + scaffold ZIPs ───────────────────────────────────
        for tier in _TIERS:
            skeleton = tier_skeletons[tier]
            deltas = tier_deltas[tier]
            tier_design = design.difficulty_tiers[tier]

            # Reconstruct gold master: inject all N function bodies into skeleton
            gold_master_files = self._inject_all_deltas(skeleton.files, deltas, language, skeleton)
            safe_gold_master = sanitizer.sanitize_generated_files(gold_master_files)

            # Hidden tests: one per scenario from deltas
            test_hidden = {tag: d.test_hidden for tag, d in deltas.items()}

            # Upload gold master ZIP (manifest.json + src/ + test-hidden/)
            storage_client.upload_gold_master_from_dict(
                safe_gold_master, test_hidden, manifest,
                challenge_name, tier, language,
            )

            # Student scaffold = skeleton (all target functions are stubs — no cross-contamination)
            safe_skeleton = sanitizer.sanitize_generated_files(skeleton.files)
            for scenario in tier_design["scenarios"]:
                tag = scenario["scenario_tag"]
                try:
                    zip_bytes = generator.generate_from_dict(
                        safe_skeleton, tag, manifest, language
                    )
                    s3_key = f"{language}/{challenge_name}-{tag}.zip"
                    storage_client.upload_bytes(
                        zip_bytes.getvalue(), settings.minio_bucket, s3_key
                    )
                    storage_client.export_scaffold_locally(
                        zip_bytes.getvalue(), challenge_name, tag, language
                    )
                    log.info(f"ScaffoldGenerator: uploaded scaffold → challenges/{s3_key}")
                except Exception as e:
                    log.error(
                        f"ScaffoldGenerator: scaffold ZIP failed for scenario={tag}: {e}"
                    )

        # ── Phase 3 — Generate and dispatch blueprints for all scenarios ──────────
        if settings.enable_blueprint_generation and settings.enable_llm:
            try:
                from services.blueprint import blueprint_service
                blueprints = blueprint_service.generate_all_scenarios(
                    challenge_name, language, manifest
                )
                for blueprint in blueprints:
                    blueprint_service.dispatch(blueprint)
                log.info(
                    f"ScaffoldGenerator: Dispatched {len(blueprints)} blueprints successfully"
                )
            except Exception as e:
                log.error(f"ScaffoldGenerator: Blueprint generation failed: {e}")

        total_scenarios = sum(
            len(design.difficulty_tiers[t]["scenarios"]) for t in _TIERS
        )
        tok = llm_client._session_tokens
        log.info(
            f"ScaffoldGenerator: complete — challenge={challenge_name}, "
            f"tiers={list(_TIERS)}, total_scenarios={total_scenarios} | "
            f"session tokens — input: {tok['input']}, cached: {tok['cached']}, "
            f"output: {tok['output']} | "
            f"total cost: ${llm_client._session_cost:.4f}"
        )
        return {"challenge": challenge_name, "language": language, "manifest": manifest}

    def _build_manifest(
        self,
        challenge_name: str,
        language: str,
        design: DesignOutput,
    ) -> dict:
        scenarios = {}
        for tier in _TIERS:
            for scenario in design.difficulty_tiers[tier]["scenarios"]:
                scenarios[scenario["scenario_tag"]] = {
                    "title": scenario["title"],
                    "description": scenario["description"],
                    "tier": tier,
                }
        return {
            "challenge": challenge_name,
            "language": language,
            "scenarios": scenarios,
        }

    def _inject_all_deltas(
        self,
        skeleton_files: dict,
        deltas: dict,
        language: str,
        tier_skeleton: "SkeletonOutput | None" = None,
    ) -> dict:
        """Inject all N function implementations into the skeleton to produce the gold master.

        First attempts an exact string replace of the stub marker. If not found (LLM used a
        different throw message and the validator accepted via the level-2 fallback), falls back
        to regex-based function-body replacement using the stub_location metadata.
        """
        result = dict(skeleton_files)
        throw_template = _STUB_THROW.get(language, _STUB_THROW["node"])
        stub_locations = tier_skeleton.stub_locations if tier_skeleton else {}

        for tag, delta in deltas.items():
            throw_stmt = throw_template.format(tag=tag)
            injected = False
            for filepath in list(result.keys()):
                if throw_stmt in result[filepath]:
                    result[filepath] = result[filepath].replace(throw_stmt, delta.function_body)
                    log.debug(f"Injected delta for {tag!r} into {filepath} (exact match)")
                    injected = True
                    break

            if not injected:
                stub_loc = stub_locations.get(tag)
                if stub_loc and stub_loc.file in result:
                    result[stub_loc.file] = _replace_function_body(
                        result[stub_loc.file],
                        stub_loc.function_name,
                        delta.function_body,
                        language,
                    )
                    log.warning(
                        f"Injected delta for {tag!r} via function-name fallback "
                        f"in {stub_loc.file!r} (function: {stub_loc.function_name!r})"
                    )
                else:
                    log.error(
                        f"Could not inject delta for {tag!r}: "
                        f"stub_loc={stub_loc}, file not in skeleton"
                    )
        return result


scaffold_generator = ScaffoldGenerator()
