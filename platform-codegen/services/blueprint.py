import json
from config.settings import settings
from infrastructure import db as db_client
from infrastructure.logger import log
from infrastructure.queue import queue_publisher
from infrastructure.storage import storage_client
from services.llm import llm_client, _count_tokens

_IGNORED = {"node_modules", "dist", "__pycache__", ".git"}
_MAX_CONTEXT_TOKENS = 60_000


class BlueprintService:
    def _build_repo_context(self, source_files: dict) -> str:
        """Build repo context string from a source files dict, up to token budget.

        Files are ordered so route/service/handler files come before boilerplate.
        Stops when adding the next file would exceed _MAX_CONTEXT_TOKENS.
        """
        if not source_files:
            return "(source not available)"

        priority_keys = [
            k for k in source_files
            if any(kw in k for kw in ("route", "service", "handler", "index"))
        ]
        other_keys = [k for k in source_files if k not in priority_keys]

        parts = []
        total_tokens = 0
        for rel_path in priority_keys + other_keys:
            if any(p in rel_path for p in _IGNORED):
                continue
            snippet = f"### {rel_path}\n```\n{source_files[rel_path]}\n```"
            t = _count_tokens(snippet)
            if total_tokens + t > _MAX_CONTEXT_TOKENS:
                log.warning(
                    f"Blueprint context budget reached at {len(parts)} files "
                    f"({total_tokens} tokens)"
                )
                break
            parts.append(snippet)
            total_tokens += t

        return "\n\n".join(parts)

    def _embed_gold_master_source(
        self,
        blueprint: dict,
        source_files: dict,
    ) -> dict:
        """Embed relevant gold master files into blueprint.repo.goldMasterSource."""
        relevant_files = blueprint.get("repo", {}).get("relevantFiles", [])
        if not relevant_files or not source_files:
            return blueprint

        gold_master_source = {}
        for entry in relevant_files:
            rel_path = entry.get("path", entry) if isinstance(entry, dict) else entry
            if rel_path in source_files:
                gold_master_source[rel_path] = source_files[rel_path]
            else:
                log.warning(f"Relevant file {rel_path!r} not found in gold master source")

        if gold_master_source:
            blueprint.setdefault("repo", {})["goldMasterSource"] = gold_master_source
            log.info(f"Embedded goldMasterSource: {list(gold_master_source.keys())}")
        return blueprint

    def generate_for_scenario(
        self,
        problem_id: str,
        challenge_name: str,
        language: str,
        scenario_tag: str,
        source_files: dict | None = None,
        manifest: dict | None = None,
        gold_master_s3_ref: str | None = None,
    ) -> dict:
        """Generate a scenario-specific blueprint.

        source_files: pre-fetched gold master source dict {rel_path: content}.
                      If None, fetched from MinIO on demand (slower).
        manifest:     challenge manifest for scenario metadata.
        """
        if source_files is None:
            tier = scenario_tag.split("-")[0] if scenario_tag else None
            if tier in ("easy", "medium", "hard", "advanced"):
                source_files = storage_client.get_gold_master_source(
                    challenge_name, tier, language
                )
            else:
                source_files = {}

        scenario_info = (manifest or {}).get("scenarios", {}).get(scenario_tag, {})

        blueprint_instructions = llm_client.load_prompt("generate_blueprint")
        repo_context = self._build_repo_context(source_files)

        # Static per scenario tier → system message (OpenAI caches this prefix)
        system = f"{blueprint_instructions}\n\n## Repository Source\n{repo_context}"
        # Dynamic per scenario → user message (tiny; changes each call)
        user = (
            f"Scenario tag: {scenario_tag}\n"
            f"Scenario title: {scenario_info.get('title', scenario_tag)}\n"
            f"What the student must fix: {scenario_info.get('description', 'See the scenario tag.')}\n"
            f"Problem ID: {problem_id}"
        )

        raw = llm_client.complete_json_cached(system, user, label=f"blueprint:{scenario_tag}")
        blueprint = json.loads(raw)
        blueprint["problemId"] = problem_id
        if gold_master_s3_ref:
            blueprint["goldMasterRef"] = gold_master_s3_ref

        blueprint = self._embed_gold_master_source(blueprint, source_files or {})
        return blueprint

    def generate_all_scenarios(
        self,
        challenge_name: str,
        language: str,
        manifest: dict,
        problem_id: str | None = None,
        gold_master_s3_refs: dict[str, str] | None = None,
    ) -> list[dict]:
        """Generate one blueprint per scenario in the manifest.

        Fetches gold master source once per tier (3 MinIO calls for 9 scenarios).
        Within a tier, all N blueprint calls share the same source context — prefix cache hit.

        gold_master_s3_refs: optional {tier: "s3://gold-masters/{lang}/{name}-{tier}.zip"}
            passed in from scaffold_generator so blueprints carry goldMasterRef without
            an extra S3 round-trip.
        """
        blueprints = []
        tiers_fetched: dict[str, dict] = {}

        for scenario_tag, scenario_info in manifest.get("scenarios", {}).items():
            tier = scenario_info.get("tier", "")
            if tier and tier not in tiers_fetched:
                tiers_fetched[tier] = storage_client.get_gold_master_source(
                    challenge_name, tier, language
                )
            source_files = tiers_fetched.get(tier, {})

            if not source_files:
                log.error(
                    f"Skipping blueprint for {scenario_tag}: gold master source is empty "
                    f"(MinIO fetch failed for tier={tier}). A blank blueprint would mislead AI eval."
                )
                continue

            pid = problem_id or f"{challenge_name}-{scenario_tag}"
            gm_ref = (gold_master_s3_refs or {}).get(tier)
            bp = self.generate_for_scenario(
                pid, challenge_name, language, scenario_tag,
                source_files=source_files,
                manifest=manifest,
                gold_master_s3_ref=gm_ref,
            )
            blueprints.append(bp)

        return blueprints

    def generate(self, problem_id: str, challenge_name: str, language: str) -> dict:
        """Legacy single-scenario generate."""
        if not settings.enable_blueprint_generation or not settings.enable_llm:
            log.warning("Blueprint generation disabled by feature flag")
            return {}

        log.info(f"Generating blueprint for {challenge_name} ({problem_id})")
        try:
            bp = self.generate_for_scenario(problem_id, challenge_name, language, problem_id)
            log.info(f"Blueprint generated successfully for {problem_id}")
            return bp
        except Exception as e:
            log.error(f"Blueprint generation failed for {problem_id}: {e}")
            return {}

    def dispatch(self, blueprint: dict):
        """Persist a blueprint via two independent paths.

        1. Postgres — direct write to problems.blueprint by slug.
        2. RabbitMQ — durable message for the backend to optionally consume.
        """
        if not blueprint:
            return

        problem_id = blueprint.get("problemId", "")

        # 1. Write directly to problems.blueprint
        try:
            db_client.save_blueprint(problem_id, blueprint)
        except Exception as e:
            log.warning(f"[blueprint] DB write failed for {problem_id} (non-fatal): {e}")

        # 2. RabbitMQ — backend may consume this for its own storage
        try:
            queue_publisher.publish(settings.blueprint_queue, blueprint)
            log.info(f"[blueprint] Queued for persistence: {problem_id}")
        except Exception as e:
            log.warning(f"[blueprint] Queue publish failed for {problem_id}: {e}")


blueprint_service = BlueprintService()
