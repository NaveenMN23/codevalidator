import json
import re
from pathlib import Path
from infrastructure.cache import cache_client
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
from services.few_shot_loader import load_few_shot_repos
from services.compile_validator import compile_validator, CompileValidationError

_JAVA_POM_TEMPLATE = (
    Path(__file__).parent.parent / "templates" / "java" / "pom.xml"
).read_text(encoding="utf-8")

_JAVA_APP_TEMPLATE = (
    Path(__file__).parent.parent / "templates" / "java" / "ChallengeApplication.java"
).read_text(encoding="utf-8")

_SUPPORTED_LANGUAGES = {"node", "java", "python"}
_TIERS = ("easy", "medium", "hard")


def _test_file_path(java_source: str) -> str | None:
    pkg = re.search(r"^\s*package\s+([\w.]+)\s*;", java_source, re.MULTILINE)
    cls = re.search(r"\bpublic\s+class\s+(\w+)", java_source)
    if not pkg or not cls:
        return None
    return f"src/test/java/{pkg.group(1).replace('.', '/')}/{cls.group(1)}.java"


def _classify_compile_error(error_output: str, delta_phase: bool = False) -> str:
    if "does not exist" in error_output and "com.challenge" in error_output:
        if delta_phase:
            return (
                "You referenced a class that does not exist in the skeleton. "
                "In this phase you cannot add new files — you can only return `function_body`. "
                "Rewrite the function body to only use classes listed in <skeleton_classes>. "
                "Do not use any class not already present in the skeleton."
            )
        return (
            "You generated code that imports from a package (e.g. com.challenge.dtos) "
            "but never generated the corresponding Java files for that package. "
            "Add ALL missing class files — every 'import com.challenge.X' must have "
            "a corresponding generated file in your output."
        )
    if "cannot find symbol" in error_output:
        if ": method" in error_output:
            return (
                "You called a method that does not exist in the class. "
                "Check <stub_file_content> for the actual methods defined there. "
                "Do not invent helper methods — implement the logic inline."
            )
        if ": class" in error_output and "com.challenge" in error_output:
            return (
                "You referenced a project class that does not exist in the skeleton. "
                "Check <skeleton_classes> for the exact class names available. "
                "Only reference classes listed there."
            )
        if ": variable" in error_output:
            # Java reports "cannot find symbol: variable Foo" when Foo is used as a type
            # but the class file was never generated.
            if delta_phase:
                return (
                    "You used a class as a type that does not exist in the skeleton. "
                    "In this phase you cannot add new files — you can only return `function_body`. "
                    "Rewrite the function body to only use classes listed in <skeleton_classes>. "
                    "Do not reference any class not already present there."
                )
            return (
                "A class is being used as a type but its .java file was never generated. "
                "Java reports this as 'cannot find symbol: variable X' when X is used as "
                "a type (e.g. return type, parameter, local variable) but does not exist "
                "in the output. Add the missing class file to your `files` output — every "
                "class referenced in the code must have a corresponding generated file."
            )
        return (
            "You used a class without importing it. "
            "Add the missing import at the top of the file "
            "(e.g. `import java.util.Optional;`, `import java.time.LocalDate;`, `import java.util.UUID;`)."
        )
    if "illegal start of expression" in error_output or "not a statement" in error_output:
        return (
            "Your code has a syntax error. "
            "Check for unclosed braces, misplaced keywords, or incomplete statements."
        )
    return "Fix the compilation error shown above before returning the corrected JSON."


def _skeleton_classes_summary(skeleton_files: dict[str, str]) -> str:
    fqns = sorted(
        m.group(1).replace("/", ".")
        for path in skeleton_files
        if (m := re.search(r"src/main/java/(.+)\.java$", path))
    )
    if not fqns:
        return ""
    lines = ["Available classes in this skeleton (ONLY reference these — do not invent class names):"]
    lines += [f"  - {fqn}" for fqn in fqns]
    return "\n".join(lines)


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

    def generate_design_only(
        self,
        problem_description: str,
        languages: list[str] | None = None,
        tiers: list[str] | None = None,
        scenarios_per_tier: int = 3,
        debug_scenarios_per_tier: int = 1,
        feedback: str | None = None,
    ) -> dict:
        """Run Phase 1 only — returns the DesignOutput as a dict for admin review."""
        active_languages = languages or ["node"]
        active_tiers = tiers or list(_TIERS)
        llm_client.reset_session_cost()
        clean_description = sanitizer.sanitize_description(problem_description)

        design_system = llm_client.load_prompt("design_challenge")
        feedback_block = f"\n\n<admin_feedback>\n{feedback}\n</admin_feedback>" if feedback else ""
        design_user_msg = (
            f"<languages>{','.join(active_languages)}</languages>\n"
            f"<tiers>{','.join(active_tiers)}</tiers>\n"
            f"<scenarios_per_tier>{scenarios_per_tier}</scenarios_per_tier>\n"
            f"<debug_scenarios_per_tier>{debug_scenarios_per_tier}</debug_scenarios_per_tier>\n"
            f"<problem>\n{clean_description}\n</problem>"
            f"{feedback_block}"
        )
        raw_design = llm_client.complete_json(design_system, design_user_msg, label="design")
        design: DesignOutput = validate_with_correction(
            raw_design, DesignOutput, llm_client.complete_json,
            design_system, design_user_msg, label="design-validate",
        )
        log.info(f"generate_design_only: complete — challenge={design.challenge.get('name')}")
        return design.model_dump()

    def generate(
        self,
        problem_description: str,
        languages: list[str] | None = None,
        use_local_few_shots: bool = False,
        tiers: list[str] | None = None,
        scenarios_per_tier: int = 3,
        debug_scenarios_per_tier: int = 1,
        design_json: str | dict | None = None,
    ) -> dict:
        active_languages: list[str] = languages or ["node"]
        active_tiers: list[str] = tiers or list(_TIERS)

        for lang in active_languages:
            if lang not in _SUPPORTED_LANGUAGES:
                raise ValueError(f"Unsupported language {lang!r}. Choose from: {_SUPPORTED_LANGUAGES}")

        llm_client.reset_session_cost()
        clean_description = sanitizer.sanitize_description(problem_description)

        few_shot_context = ""
        if use_local_few_shots:
            few_shot_context = load_few_shot_repos() + "\n"

        # ── Phase 1 — Architecture Design (skip if design_json supplied by admin) ─
        if design_json is not None:
            import json as _json
            raw = design_json if isinstance(design_json, str) else _json.dumps(design_json)
            design: DesignOutput = DesignOutput.model_validate_json(raw)
            log.info(f"ScaffoldGenerator: Phase 1 skipped — using pre-approved design")
        else:
            design_system = llm_client.load_prompt("design_challenge")
            log.info(f"ScaffoldGenerator: Phase 1 (design, tiers={active_tiers}, scenarios_per_tier={scenarios_per_tier}, debug_scenarios_per_tier={debug_scenarios_per_tier})")
            design_user_msg = (
                f"<languages>{','.join(active_languages)}</languages>\n"
                f"<tiers>{','.join(active_tiers)}</tiers>\n"
                f"<scenarios_per_tier>{scenarios_per_tier}</scenarios_per_tier>\n"
                f"<debug_scenarios_per_tier>{debug_scenarios_per_tier}</debug_scenarios_per_tier>\n"
                f"<problem>\n{clean_description}\n</problem>"
            )
            raw_design = llm_client.complete_json(design_system, design_user_msg, label="design")
            design: DesignOutput = validate_with_correction(
                raw_design, DesignOutput, llm_client.complete_json,
                design_system, design_user_msg, label="design-validate",
            )

        # Verify the LLM produced the requested tiers with the right scenario count
        for tier in active_tiers:
            if tier not in design.difficulty_tiers:
                raise ValueError(
                    f"Design output missing tier '{tier}' — got: {list(design.difficulty_tiers.keys())}"
                )
            actual_count = len(design.difficulty_tiers[tier].get("scenarios", []))
            if actual_count != scenarios_per_tier:
                raise ValueError(
                    f"Tier '{tier}' has {actual_count} scenarios, expected {scenarios_per_tier}"
                )

        challenge_name = design.challenge.get("name", "challenge")
        log.info(f"ScaffoldGenerator: Phase 1 complete — challenge={challenge_name}")

        # ── Phase 2 — Per language: skeleton + deltas + upload ───────────────────
        all_manifests: dict[str, dict] = {}
        failed_scaffolds: list[str] = []
        failed_blueprints: list[str] = []
        generated_blueprints: dict[str, dict] = {}

        for language in active_languages:
            log.info(f"ScaffoldGenerator: Phase 2 start — language={language}")
            skipped_tiers: set[str] = set()

            # Phase 2a — Skeleton per tier
            skeleton_system = llm_client.load_prompt(f"implement_skeleton_{language}")
            tier_skeletons: dict[str, SkeletonOutput] = {}

            for tier in active_tiers:
                checkpoint_key = f"codegen:checkpoint:{challenge_name}:{language}:{tier}"
                if cache_client.get(checkpoint_key) == "completed":
                    log.info(f"ScaffoldGenerator: checkpoint hit — skipping tier={tier} lang={language}")
                    skipped_tiers.add(tier)
                    continue

                tier_design = design.difficulty_tiers[tier]
                scenarios_json = json.dumps(tier_design["scenarios"], indent=2)
                user_context = (
                    f"{few_shot_context}"
                    f"<problem>\n{clean_description}\n</problem>\n\n"
                    f"<design>\n{json.dumps(design.model_dump(), indent=2)}\n</design>\n\n"
                    f"<tier>{tier.upper()}</tier>\n"
                    f"<scenarios>\n{scenarios_json}\n</scenarios>"
                )
                scenario_tags = [s["scenario_tag"] for s in tier_design["scenarios"]]
                log.info(f"ScaffoldGenerator: Phase 2a skeleton — lang={language}, tier={tier}, scenarios={scenario_tags}")
                raw_skeleton = llm_client.complete_json_cached(
                    skeleton_system,
                    user_context,
                    label=f"skeleton-{language}-{tier}",
                    max_tokens_override=settings.openai_max_tokens_impl,
                )
                skeleton: SkeletonOutput = validate_with_correction(
                    raw_skeleton,
                    SkeletonOutput,
                    lambda sys, usr, l=language, t=tier: llm_client.complete_json_cached(
                        sys, usr,
                        label=f"skeleton-{l}-{t}-retry",
                        max_tokens_override=settings.openai_max_tokens_impl,
                    ),
                    skeleton_system,
                    user_context,
                    label=f"skeleton-{language}-{tier}-validate",
                )
                if language == "java":
                    skeleton.files["pom.xml"] = _JAVA_POM_TEMPLATE
                    skeleton.files["src/main/java/com/challenge/ChallengeApplication.java"] = _JAVA_APP_TEMPLATE
                    log.info("ScaffoldGenerator: injected pinned pom.xml + ChallengeApplication.java (java)")
                tier_skeletons[tier] = skeleton
                log.info(f"ScaffoldGenerator: Phase 2a done — lang={language}, tier={tier}, files={list(skeleton.files.keys())}")

                # Validate the skeleton compiles before Phase 2b (catches missing DTO/model files)
                skeleton_compile_attempt = 0
                skeleton_compile_context = user_context
                while True:
                    try:
                        compile_validator.validate_compilation(skeleton.files, language)
                        log.info(f"ScaffoldGenerator: skeleton compiled OK — lang={language}, tier={tier}")
                        break
                    except CompileValidationError as e:
                        if skeleton_compile_attempt >= 1:
                            log.error(f"ScaffoldGenerator: skeleton compilation failed after 2 attempts for lang={language}, tier={tier}")
                            raise
                        skeleton_compile_attempt += 1
                        hint = _classify_compile_error(str(e))
                        log.warning(f"ScaffoldGenerator: skeleton compile failed — {hint}. Regenerating skeleton.")
                        skeleton_compile_context = (
                            f"{user_context}\n\n"
                            f"Your previous skeleton failed to compile:\n{e}\n\n"
                            f"How to fix: {hint}\n\n"
                            f"Regenerate the complete skeleton with all missing files included."
                        )
                        raw_skeleton = llm_client.complete_json_cached(
                            skeleton_system,
                            skeleton_compile_context,
                            label=f"skeleton-{language}-{tier}-compile-retry",
                            max_tokens_override=settings.openai_max_tokens_impl,
                        )
                        skeleton = validate_with_correction(
                            raw_skeleton,
                            SkeletonOutput,
                            lambda sys, usr, l=language, t=tier: llm_client.complete_json_cached(
                                sys, usr,
                                label=f"skeleton-{l}-{t}-compile-retry-schema",
                                max_tokens_override=settings.openai_max_tokens_impl,
                            ),
                            skeleton_system,
                            skeleton_compile_context,
                            label=f"skeleton-{language}-{tier}-compile-retry-validate",
                        )
                        if language == "java":
                            skeleton.files["pom.xml"] = _JAVA_POM_TEMPLATE
                        tier_skeletons[tier] = skeleton
                        log.info(f"ScaffoldGenerator: skeleton regenerated — lang={language}, tier={tier}, files={list(skeleton.files.keys())}")

            # Phase 2b — Function deltas per scenario
            tier_deltas: dict[str, dict[str, FunctionDeltaOutput]] = {}

            for tier in active_tiers:
                if tier in skipped_tiers:
                    continue
                skeleton = tier_skeletons[tier]
                tier_design = design.difficulty_tiers[tier]
                tier_deltas[tier] = {}

                for scenario in tier_design["scenarios"]:
                    tag = scenario["scenario_tag"]
                    scenario_type = scenario.get("type", "implement")
                    prompt_name = (
                        f"debug_function_{language}" if scenario_type == "debug"
                        else f"implement_function_{language}"
                    )
                    function_system = llm_client.load_prompt(prompt_name)
                    stub_loc = skeleton.stub_locations.get(tag)
                    stub_file_content = (
                        skeleton.files.get(stub_loc.file, "") if stub_loc else ""
                    )
                    user_context = (
                        f"<tier>{tier.upper()}</tier>\n"
                        f"<scenario_tag>{tag}</scenario_tag>\n"
                        f"<scenario_title>{scenario['title']}</scenario_title>\n"
                        f"<scenario_description>{scenario['description']}</scenario_description>\n"
                        f"<bug_description>{scenario.get('bug_description', '')}</bug_description>\n"
                        f"<strip_description>{scenario.get('strip_description', '')}</strip_description>\n"
                        f"<stub_file>{stub_loc.file if stub_loc else ''}</stub_file>\n"
                        f"<stub_file_content>\n{stub_file_content}\n</stub_file_content>\n"
                        f"<full_skeleton>\n{json.dumps(skeleton.files, indent=2)}\n</full_skeleton>\n"
                        f"<skeleton_classes>\n{_skeleton_classes_summary(skeleton.files)}\n</skeleton_classes>"
                    )
                    delta_system = function_system
                    delta_user_context = user_context
                    attempt = 0
                    max_attempts = 3
                    delta = None
                    
                    while attempt <= max_attempts:
                        raw_delta = llm_client.complete_json(
                            delta_system,
                            delta_user_context,
                            label=f"function-{language}-{tag}-att{attempt}",
                            max_tokens_override=settings.openai_max_tokens_test,
                        )
                        delta = validate_with_correction(
                            raw_delta,
                            FunctionDeltaOutput,
                            llm_client.complete_json,
                            delta_system,
                            delta_user_context,
                            label=f"function-{language}-{tag}-validate",
                        )
                        
                        # Validate compilation for this delta specifically
                        test_files = self._inject_all_deltas(skeleton.files, {tag: delta}, language, skeleton)
                        safe_test_files = sanitizer.sanitize_generated_files(test_files)
                        try:
                            compile_validator.validate_compilation(safe_test_files, language)
                            break # Success!
                        except CompileValidationError as e:
                            attempt += 1
                            if attempt > max_attempts:
                                log.error(f"ScaffoldGenerator: Delta compilation failed after {max_attempts} attempts for scenario={tag}")
                                raise e
                            log.warning(f"Delta compilation failed (attempt {attempt}): {e}. Sending compiler error to LLM for correction.")
                            targeted_hint = _classify_compile_error(str(e), delta_phase=True)
                            delta_user_context = (
                                f"{user_context}\n\n"
                                f"Your previous implementation caused a compilation error:\n{e}\n\n"
                                f"How to fix: {targeted_hint}\n\n"
                                f"Please return the corrected JSON with all issues resolved."
                            )
                    tier_deltas[tier][tag] = delta
                    log.info(f"ScaffoldGenerator: Phase 2b done — lang={language}, scenario={tag}")

            # Build manifest for this language
            manifest = self._build_manifest(challenge_name, language, design, active_tiers)
            all_manifests[language] = manifest

            # Upload gold masters + scaffold ZIPs
            gold_master_s3_refs: dict[str, str] = {}  # tier → s3:// URI, built as each upload succeeds
            for tier in active_tiers:
                if tier in skipped_tiers:
                    continue
                skeleton = tier_skeletons[tier]
                deltas = tier_deltas[tier]
                tier_design = design.difficulty_tiers[tier]

                gold_master_files = self._inject_all_deltas(skeleton.files, deltas, language, skeleton)
                safe_gold_master = sanitizer.sanitize_generated_files(gold_master_files)
                test_hidden = {tag: d.test_hidden for tag, d in deltas.items()}

                try:
                    compile_validator.validate_compilation(safe_gold_master, language)
                except CompileValidationError as e:
                    error_msg = f"ScaffoldGenerator: compile validation failed tier={tier} lang={language}: {e}"
                    log.error(error_msg)
                    raise RuntimeError(error_msg)

                try:
                    storage_client.upload_gold_master_from_dict(
                        safe_gold_master, test_hidden, manifest,
                        challenge_name, tier, language,
                    )
                    gold_master_s3_refs[tier] = f"s3://gold-masters/{language}/{challenge_name}-{tier}.zip"
                except Exception as e:
                    error_msg = f"ScaffoldGenerator: gold master upload failed tier={tier} lang={language}: {e}"
                    log.error(error_msg)
                    raise RuntimeError(error_msg)

                safe_skeleton = sanitizer.sanitize_generated_files(skeleton.files)
                for scenario in tier_design["scenarios"]:
                    tag = scenario["scenario_tag"]
                    try:
                        scaffold_files = dict(safe_skeleton)
                        delta = tier_deltas[tier].get(tag)
                        if delta and delta.test_visible:
                            visible_path = _test_file_path(delta.test_visible)
                            if visible_path:
                                scaffold_files[visible_path] = delta.test_visible
                                log.info(f"ScaffoldGenerator: added visible test → {visible_path}")
                        zip_bytes = generator.generate_from_dict(scaffold_files, tag, manifest, language)
                        s3_key = f"{language}/{challenge_name}-{tag}.zip"
                        storage_client.upload_bytes(zip_bytes.getvalue(), settings.aws_s3_challenges_bucket, s3_key)
                        storage_client.export_scaffold_locally(zip_bytes.getvalue(), challenge_name, tag, language)
                        log.info(f"ScaffoldGenerator: uploaded scaffold → challenges/{s3_key}")
                    except Exception as e:
                        error_msg = f"ScaffoldGenerator: scaffold ZIP failed for scenario={tag} lang={language}: {e}"
                        log.error(error_msg)
                        raise RuntimeError(error_msg)

                if not failed_scaffolds:
                    try:
                        checkpoint_key = f"codegen:checkpoint:{challenge_name}:{language}:{tier}"
                        cache_client.set(checkpoint_key, "completed", expire=60 * 60 * 24)
                        log.info(f"ScaffoldGenerator: checkpoint written for tier={tier} lang={language}")
                    except Exception as e:
                        log.warning(f"ScaffoldGenerator: failed to write checkpoint tier={tier} lang={language}: {e}")

            # Phase 3 — Blueprints (language-level, after all tiers)
            if settings.enable_blueprint_generation and settings.enable_llm:
                try:
                    from services.blueprint import blueprint_service
                    blueprints = blueprint_service.generate_all_scenarios(
                        challenge_name, language, manifest,
                        gold_master_s3_refs=gold_master_s3_refs,
                    )
                    for bp in blueprints:
                        blueprint_service.dispatch(bp)  # best-effort: succeeds if problem row already exists
                        generated_blueprints[bp["problemId"]] = bp
                    log.info(f"ScaffoldGenerator: Generated {len(blueprints)} blueprints for lang={language}")
                except Exception as e:
                    log.error(f"ScaffoldGenerator: Blueprint generation failed for lang={language}: {e}")
                    failed_blueprints.append(language)

            log.info(f"ScaffoldGenerator: Phase 2 complete — language={language}")

        total_scenarios = sum(
            len(design.difficulty_tiers[t]["scenarios"]) for t in active_tiers
        )
        tok = llm_client._session_tokens
        log.info(
            f"ScaffoldGenerator: complete — challenge={challenge_name}, "
            f"languages={active_languages}, tiers={active_tiers}, "
            f"scenarios_per_tier={scenarios_per_tier}, total_scenarios={total_scenarios} | "
            f"session tokens — input: {tok['input']}, cached: {tok['cached']}, "
            f"output: {tok['output']} | "
            f"total cost: ${llm_client._session_cost:.4f}"
        )
        return {
            "challenge": challenge_name,
            "languages": active_languages,
            "tiers": active_tiers,
            "scenarios_per_tier": scenarios_per_tier,
            "manifests": all_manifests,
            "blueprints": generated_blueprints,
            "usage": {
                "input_tokens": tok["input"],
                "cached_tokens": tok["cached"],
                "output_tokens": tok["output"],
                "total_cost_usd": round(llm_client._session_cost, 4),
            },
            "warnings": {
                "failed_scaffolds": failed_scaffolds,
                "failed_blueprints": failed_blueprints,
            },
        }
    def _build_manifest(
        self,
        challenge_name: str,
        language: str,
        design: DesignOutput,
        active_tiers: list[str] | None = None,
    ) -> dict:
        tiers_to_use = active_tiers or list(_TIERS)
        scenarios = {}
        for tier in tiers_to_use:
            for scenario in design.difficulty_tiers[tier]["scenarios"]:
                scenarios[scenario["scenario_tag"]] = {
                    "title": scenario["title"],
                    "description": scenario["description"],
                    "tier": tier,
                    "type": scenario.get("type", "implement"),
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

            # Try DEBUG_SCENARIO marker (debug-type scenarios have broken code, not a stub throw)
            if not injected:
                debug_marker = f"DEBUG_SCENARIO: {tag}"
                for filepath in list(result.keys()):
                    if debug_marker in result[filepath]:
                        stub_loc = stub_locations.get(tag)
                        if stub_loc and stub_loc.function_name:
                            result[filepath] = _replace_function_body(
                                result[filepath],
                                stub_loc.function_name,
                                delta.function_body,
                                language,
                            )
                            log.debug(f"Injected debug fix for {tag!r} into {filepath} (DEBUG_SCENARIO marker)")
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
