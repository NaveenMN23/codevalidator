import re

MAX_DESCRIPTION_CHARS = 5_000
MAX_FILE_SIZE_BYTES = 50 * 1024  # 50 KB per generated file

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"\bsystem\s*:",
    r"\bassistant\s*:",
    r"<\|im_(end|start)\|>",
    r"---\s*\n\s*role\s*:",
]


class InputSanitizer:
    def sanitize_description(self, text: str) -> str:
        text = text.strip()
        if not text:
            raise ValueError("Problem description must not be empty")
        if len(text) > MAX_DESCRIPTION_CHARS:
            raise ValueError(f"Description exceeds {MAX_DESCRIPTION_CHARS} chars (got {len(text)})")
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                raise ValueError("Prompt injection pattern detected in input")
        return text

    def sanitize_file_path(self, path: str) -> str:
        if ".." in path or path.startswith("/") or path.startswith("\\"):
            raise ValueError(f"Unsafe file path rejected: {path!r}")
        return path

    def sanitize_generated_files(self, files: dict) -> dict:
        result = {}
        for path, content in files.items():
            safe_path = self.sanitize_file_path(path)
            if not isinstance(content, str):
                raise ValueError(f"File content must be a string: {path!r}")
            content_bytes = content.encode("utf-8", errors="strict")
            if len(content_bytes) > MAX_FILE_SIZE_BYTES:
                raise ValueError(
                    f"Generated file {path!r} exceeds 50 KB ({len(content_bytes)} bytes) — possible hallucination"
                )
            result[safe_path] = content
        return result


sanitizer = InputSanitizer()
