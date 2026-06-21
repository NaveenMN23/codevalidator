import os
import sys
import argparse
from pathlib import Path

# Add the parent directory to sys.path so we can import from services
sys.path.append(str(Path(__file__).parent.parent))

from services.scaffold_generator import scaffold_generator
from infrastructure.logger import log

def main():
    parser = argparse.ArgumentParser(description="Generate a golden repo locally using few-shot examples.")
    parser.add_argument("--prompt", required=True, help="The problem description/prompt")
    parser.add_argument("--language", default="java", choices=["java", "node", "python"], help="Target language")
    args = parser.parse_args()

    log.info(f"Starting local few-shot generation for {args.language}")
    log.info(f"Prompt: {args.prompt}")

    try:
        result = scaffold_generator.generate(
            problem_description=args.prompt,
            language=args.language,
            use_local_few_shots=True
        )
        usage = result.get('usage', {})
        log.info(f"Successfully generated golden repo: {result['challenge']}")
        log.info(f"Usage metrics: {usage}")
    except Exception as e:
        log.error(f"Generation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
