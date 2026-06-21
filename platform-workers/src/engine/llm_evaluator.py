import anthropic
import json
from loguru import logger
from src.config import settings
from typing import Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from anthropic import APIConnectionError, APITimeoutError, RateLimitError

class LLMEvaluator:
    def __init__(self):
        # Increase timeout to 90 seconds for better stability
        self.client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=90.0
        )
        self.model = "claude-3-haiku-20240307"

    def _filter_files(self, submission_files: Dict[str, str], blueprint: Dict[str, Any]) -> str:
        """
        Filters the submission files to only include relevant files from the blueprint.
        Excludes large folders, binary files, and caps total size.
        """
        repo_config = blueprint.get("repo", {})
        relevant_files = set(repo_config.get("relevantFiles", []))
        target_file = repo_config.get("targetFile")
        if target_file:
            relevant_files.add(target_file)

        filtered_data = {}
        total_chars = 0
        MAX_CHARS = 50000 # ~12k-15k tokens limit for the diff part

        # Sort keys for consistent hashing/caching later
        for path in sorted(submission_files.keys()):
            # Explicit exclusion list
            if any(part in path.split("/") for part in ["node_modules", "dist", ".git", ".idea", "target", "build"]):
                continue
            
            # If relevant files are specified, only include those. Otherwise include all non-excluded.
            if relevant_files and path not in relevant_files:
                continue
                
            content = submission_files[path]
            
            # Skip likely binary files or extremely large individual files
            if len(content) > 20000: # 20KB limit per file
                continue

            if total_chars + len(content) > MAX_CHARS:
                logger.warning(f"Payload size limit reached, skipping remaining files starting with {path}")
                break
                
            filtered_data[path] = content
            total_chars += len(content)

        return json.dumps(filtered_data, indent=2)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError, RateLimitError, ConnectionError)),
        reraise=True
    )
    def _create_message(self, system_prompt: str, blueprint: Dict[str, Any], submission_diff: str):
        return self.client.beta.prompt_caching.messages.create(
            model=self.model,
            max_tokens=2000,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"BLUEPRINT CONTEXT:\n{json.dumps(blueprint)}",
                            "cache_control": {"type": "ephemeral"}
                        },
                        {
                            "type": "text",
                            "text": f"CANDIDATE DIFF:\n{submission_diff}"
                        }
                    ]
                }
            ]
        )

    def evaluate(self, 
                 blueprint: Dict[str, Any], 
                 submission_diff: str, 
                 remaining_time: int,
                 user_type: str) -> Dict[str, Any]:
        """
        Evaluates the candidate's diff against the blueprint using Anthropic's Claude 3 Haiku.
        Leverages Prompt Caching for the static blueprint context to reduce latency and cost.
        """
        logger.info(f"Starting LLM evaluation for user type: {user_type} (Time remaining: {remaining_time}s)")
        
        # Determine follow-up type based on time (Phase 4 logic)
        follow_up_type = "IMPLEMENTATION" if remaining_time > 900 else "CONVERSATIONAL"
        
        system_prompt = f"""You are a senior software engineer interviewer.
Evaluate the candidate's code submission (diff) against the provided Blueprint.

TASK DESCRIPTION: {blueprint.get('task', {}).get('description', 'N/A')}
CONSTRAINTS: {blueprint.get('task', {}).get('constraints', [])}
EXPECTED COMPLEXITY: {blueprint.get('task', {}).get('expectedComplexity', {})}
SCOPE: {blueprint.get('scope', {})}
EXPECTED APPROACHES: {blueprint.get('expectedApproaches', [])}
INTERVIEWER FOCUS: {blueprint.get('interviewFocusArea') or blueprint.get('interviewerFocusArea', 'N/A')}

You must provide feedback in three layers:
1. Correctness Finding
2. Efficiency Finding
3. Interviewer Follow-up (Persona-driven)

The Follow-up must be of type: {follow_up_type}.
For B2C users, focus on coaching and blind spots.
For B2B users, focus on seniority signal and hiring manager summary.

RESPONSE FORMAT (Strict JSON):
{{
    "correctness": {{ "finding": "string", "score": 0-10 }},
    "efficiency": {{ "finding": "string", "score": 0-10 }},
    "followUp": {{ "type": "{follow_up_type}", "content": "string" }},
    "summary": "string"
}}
"""

        try:
            # Construct message with Prompt Caching (Beta) via retried method
            message = self._create_message(system_prompt, blueprint, submission_diff)
            
            # Extract JSON from response
            response_text = message.content[0].text
            # Basic cleanup if LLM adds markdown triple backticks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
                
            return json.loads(response_text)
            
        except Exception as e:
            logger.exception(f"LLM Evaluation failed for submission")
            return {
                "error": str(e),
                "success": False,
                "summary": "AI Evaluation failed due to an internal error."
            }
