import io
import os
import re
import zipfile
import json
from pathlib import Path
from infrastructure.logger import log

class ChallengeGenerator:
    def __init__(self, challenges_base_dir: Path):
        self.base_dir = challenges_base_dir
        self.ignore_patterns = [
            'node_modules', 'dist', 'database.db', 'package-lock.json',
            'venv', '__pycache__', '.DS_Store', '.git', 'vitest.config.ts',
            'test-hidden',
        ]

    def _get_manifest(self, challenge_name: str) -> dict:
        manifest_path = self.base_dir / challenge_name / "manifest.json"
        if not manifest_path.exists():
            log.warning(f"Manifest not found for {challenge_name}")
            return {}
        with open(manifest_path, 'r') as f:
            return json.load(f)

    def generate(
        self,
        challenge_name: str,
        language: str,
        tags: list,
        tier: str = None,
    ) -> Path:
        """Generate a student-facing scaffold ZIP by stripping @strip-target blocks.

        tier: if provided, reads from gold-master-{tier}-{language}/ instead of gold-master-{language}/
        """
        gold_master_dir = f"gold-master-{tier}-{language}" if tier else f"gold-master-{language}"
        source_dir = self.base_dir / challenge_name / "apps" / gold_master_dir
        dist_dir = self.base_dir / challenge_name / "dist" / language

        if not source_dir.exists():
            raise FileNotFoundError(f"Source directory {source_dir} not found")

        dist_dir.mkdir(parents=True, exist_ok=True)
        # Unique filename based on tags
        file_suffix = "-".join(sorted(tags))
        output_path = dist_dir / f"{file_suffix}.zip"

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(source_dir):
                # Prune directories in-place to skip them
                dirs[:] = [d for d in dirs if d not in self.ignore_patterns]
                
                for file in files:
                    if file in self.ignore_patterns:
                        continue
                    
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(source_dir)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Apply multi-tag stripping logic
                        content = self._process_content(content, tags)
                        zip_file.writestr(str(relative_path), content)
                    except (UnicodeDecodeError, PermissionError):
                        zip_file.write(file_path, relative_path)

            # Generate dynamic README
            manifest = self._get_manifest(challenge_name)
            readme_content = self._build_readme(challenge_name, tags, manifest)
            zip_file.writestr("README.md", readme_content)

        log.info(f"Generated challenge zip: {output_path}")
        return output_path

    def generate_from_dict(
        self,
        files: dict,
        scenario_tag: str,
        manifest: dict,
        language: str = "node",
    ) -> io.BytesIO:
        """Generate a student scaffold ZIP from in-memory skeleton files.

        Replaces the stub throw/raise statement for this scenario with a TODO comment.
        Other stubs are left as-is — showing the function signature without the answer.
        Adds a scenario-specific README.
        """
        stub_patterns = {
            "node": (
                f"throw new Error('not implemented: {scenario_tag}');",
                "// TODO: implement this function",
            ),
            "java": (
                f'throw new UnsupportedOperationException("not implemented: {scenario_tag}");',
                "// TODO: implement this method",
            ),
            "python": (
                f'raise NotImplementedError("not implemented: {scenario_tag}")',
                "# TODO: implement this function",
            ),
        }
        target_stub, todo = stub_patterns.get(language, stub_patterns["node"])

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel_path, content in files.items():
                if rel_path == "README.md":
                    continue
                content = content.replace(target_stub, todo)
                zf.writestr(rel_path, content)

            readme_content = self._build_readme(
                manifest.get("challenge", "challenge"), [scenario_tag], manifest
            )
            zf.writestr("README.md", readme_content)

        zip_buffer.seek(0)
        return zip_buffer

    def _process_content(self, content: str, target_tags: list) -> str:
        # Pass 1: Strip code for any tag in target_tags
        for tag in target_tags:
            target_regex = fr'(//|#) @strip-target: {tag}[\s\S]*?(\1) @strip-end'
            def strip_replace(match):
                prefix = match.group(1)
                return f"{prefix} [REMOVED FOR CHALLENGE: {tag}]"
            content = re.sub(target_regex, strip_replace, content)

        # Pass 2: Clean up remaining tag markers but keep code
        all_tags_regex = r'(//|#) @strip-target:.*[\s\S]*?(//|#) @strip-end'
        def clean_tags(match):
            m = match.group(0)
            m = re.sub(r'(//|#) @strip-target:.*\n?', '', m)
            m = re.sub(r'(//|#) @strip-end\n?', '', m)
            return m
        content = re.sub(all_tags_regex, clean_tags, content)
        
        return content

    def _build_readme(self, challenge_name: str, tags: list, manifest: dict) -> str:
        scenarios = manifest.get("scenarios", {})
        
        problems_md = ""
        for tag in tags:
            scenario = scenarios.get(tag, {})
            title = scenario.get("title", tag)
            desc = scenario.get("description", "Investigate and fix the issue.")
            problems_md += f"### {title}\n{desc}\n\n"

        return f"""# Challenge: {challenge_name.replace('-', ' ').title()}

## Problem Overview
This is a comprehensive challenge involving multiple scenarios.

## Tasks to Solve
{problems_md}

## Your Task
1. Diagnose the root cause of the failures by running the tests.
2. Navigate the codebase to find the relevant services.
3. Implement the fixes to ensure all business requirements are met.
4. Ensure all integration tests pass.

## How to Run
1. Install dependencies: `npm install`
2. Run tests: `npm test`
"""

# Singleton instance
BASE_DIR = Path(__file__).parent.parent.parent / "challenges"
generator = ChallengeGenerator(BASE_DIR)
