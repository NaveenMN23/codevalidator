"""
Resolver abstraction: blueprint + gold-master → scoped file-maps.
Eval core never sees a zip; it only gets {path: content} dicts.
"""
from __future__ import annotations
import io
import json
import os
import zipfile
from pathlib import Path
from infrastructure.logger import log
from infrastructure.cache import cache_client
from infrastructure.store import session_store

_MAX_TOTAL_BYTES = 50_000   # 50KB total
_MAX_FILE_BYTES = 20_000    # 20KB per file

_WORKSPACE_ROOT = Path(__file__).parent.parent.parent  # repo root


def _filter_files(files: dict[str, str], blueprint: dict) -> dict[str, str]:
    """
    Caps payload at 50KB total / 20KB per file, sorted keys.
    Uses blueprint.relevantFiles if present; otherwise passes all files through the cap.
    """
    relevant_paths: set[str] = set()
    repo = blueprint.get("repo", {})
    for entry in repo.get("relevantFiles", []):
        if isinstance(entry, dict):
            relevant_paths.add(entry.get("path", ""))
        elif isinstance(entry, str):
            relevant_paths.add(entry)
    target = blueprint.get("task", {}).get("targetFile", "")
    if target:
        relevant_paths.add(target)

    candidates = (
        {k: v for k, v in files.items() if k in relevant_paths}
        if relevant_paths
        else files
    )

    result: dict[str, str] = {}
    total_bytes = 0
    for path in sorted(candidates.keys()):
        content = candidates[path]
        encoded = content.encode("utf-8")
        if len(encoded) > _MAX_FILE_BYTES:
            encoded = encoded[:_MAX_FILE_BYTES]
            content = encoded.decode("utf-8", errors="replace")
        if total_bytes + len(encoded) > _MAX_TOTAL_BYTES:
            break
        result[path] = content
        total_bytes += len(encoded)

    return result


def _normalize_path(path: str) -> str:
    """Remove duplicate src/ prefix (src/src/... quirk in some gold-masters)."""
    parts = path.split("/")
    deduped = []
    for p in parts:
        if deduped and deduped[-1] == p:
            continue
        deduped.append(p)
    return "/".join(deduped)


def _unzip_to_file_map(zip_bytes: bytes) -> dict[str, str]:
    file_map: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            try:
                content = zf.read(name).decode("utf-8", errors="replace")
            except Exception:
                continue
            normalized = _normalize_path(name)
            file_map[normalized] = content
    return file_map


class BlueprintSource:
    """Resolves the blueprint DTO for a given problemId."""

    def resolve(self, problem_id: str) -> dict:
        # 1. Redis (short-lived read cache — 1 hour TTL)
        cached = cache_client.get(f"blueprint:{problem_id}")
        if cached:
            try:
                data = json.loads(cached)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

        # 2. Postgres (primary durable store)
        row = session_store.load_blueprint(problem_id)
        if row:
            log.info(f"Blueprint loaded from Postgres: {problem_id}")
            try:
                cache_client.set(f"blueprint:{problem_id}", json.dumps(row), expire=3600)
            except Exception:
                pass
            return row

        # 3. Local FS (dev fallback — backfills Postgres on first load)
        local_paths = [
            _WORKSPACE_ROOT / "blueprint" / f"{problem_id}.json",
            _WORKSPACE_ROOT / "platform-eval" / "blueprint" / f"{problem_id}.json",
        ]
        for path in local_paths:
            if path.exists():
                log.info(f"Blueprint loaded from local FS: {path}")
                data = json.loads(path.read_text())
                try:
                    session_store.save_blueprint(problem_id, data)
                    log.info(f"Blueprint backfilled to Postgres from FS: {problem_id}")
                except Exception as e:
                    log.warning(f"Postgres backfill failed for {problem_id}: {e}")
                return data

        raise FileNotFoundError(
            f"Blueprint not found for problemId={problem_id}. "
            f"Check Postgres blueprints table, Redis key 'blueprint:{problem_id}', "
            f"or local FS paths: {local_paths}"
        )


class SolutionSource:
    """Resolves the gold-master file map from a ref (S3 URL or local path)."""

    def resolve(self, gold_master_ref: str, blueprint: dict) -> dict[str, str]:
        if not gold_master_ref:
            return {}

        if gold_master_ref.startswith("s3://"):
            return self._resolve_s3(gold_master_ref, blueprint)

        # Dev: local file path or constructed path
        path = Path(gold_master_ref)
        if not path.exists():
            # Try relative to workspace root
            path = _WORKSPACE_ROOT / gold_master_ref
        if path.exists() and path.suffix == ".zip":
            log.info(f"Gold-master loaded from local zip: {path}")
            zip_bytes = path.read_bytes()
            file_map = _unzip_to_file_map(zip_bytes)
            return _filter_files(file_map, blueprint)

        log.warning(f"Gold-master not found at {gold_master_ref} — returning empty")
        return {}

    def _resolve_s3(self, s3_url: str, blueprint: dict) -> dict[str, str]:
        import urllib.request
        # Convert s3:// → https URL (assumes public or pre-signed)
        https_url = s3_url.replace("s3://", "https://s3.amazonaws.com/", 1)
        log.info(f"Fetching gold-master from S3: {https_url}")
        with urllib.request.urlopen(https_url, timeout=30) as resp:
            zip_bytes = resp.read()
        file_map = _unzip_to_file_map(zip_bytes)
        return _filter_files(file_map, blueprint)


blueprint_source = BlueprintSource()
solution_source = SolutionSource()
