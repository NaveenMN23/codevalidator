import os
import zipfile
from pathlib import Path
from infrastructure.logger import log

def load_few_shot_repos(
    directory: str = "few_shots",
    max_repos: int = 3,
    max_total_chars: int = 30_000,
) -> str:
    """
    Scans the given directory for ZIP files, extracts text-based source files
    (skipping binaries, .class, .idea, .git, etc.), and formats them as XML.
    Stops loading once max_total_chars of file content has been accumulated.
    Returns the formatted XML string.
    """
    base_dir = Path(__file__).parent.parent / directory
    if not base_dir.exists() or not base_dir.is_dir():
        log.warning(f"Few-shot directory {base_dir} not found. Skipping.")
        return ""

    zip_files = list(base_dir.glob("*.zip"))
    if not zip_files:
        log.info(f"No ZIP files found in {base_dir}. Skipping few-shot loading.")
        return ""

    zip_files = zip_files[:max_repos]
    log.info(f"Loading up to {len(zip_files)} few-shot repositories from {base_dir} (budget: {max_total_chars} chars)...")

    skip_extensions = {".class", ".jar", ".png", ".jpg", ".jpeg", ".ico", ".pdf", ".zip", ".tar", ".gz"}
    skip_dirs = {".git", ".idea", ".vscode", "target", "node_modules", "dist", "build"}

    output_lines = ["<few_shot_examples>"]
    total_chars = 0

    for zip_path in zip_files:
        if total_chars >= max_total_chars:
            break
        output_lines.append(f'  <repository name="{zip_path.name}">')
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                for file_info in z.infolist():
                    if file_info.is_dir():
                        continue
                    if total_chars >= max_total_chars:
                        break

                    filename = file_info.filename
                    if any(f"/{d}/" in f"/{filename}" for d in skip_dirs):
                        continue

                    ext = os.path.splitext(filename)[1].lower()
                    if ext in skip_extensions:
                        continue

                    try:
                        content = z.read(file_info).decode('utf-8')
                        if total_chars + len(content) > max_total_chars:
                            # Take only what fits
                            remaining = max_total_chars - total_chars
                            content = content[:remaining]
                        total_chars += len(content)
                        output_lines.append(f'    <file path="{filename}">')
                        output_lines.append(content)
                        output_lines.append(f'    </file>')
                    except UnicodeDecodeError:
                        continue
        except Exception as e:
            log.error(f"Error reading zip {zip_path.name}: {e}")

        output_lines.append(f'  </repository>')

    log.info(f"Few-shot context loaded: {total_chars} chars total")
    output_lines.append("</few_shot_examples>")
    return "\n".join(output_lines)
