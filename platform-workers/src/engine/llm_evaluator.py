import json
from loguru import logger
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from typing import Dict, Any, Optional
from src.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class _HiringAssessment(BaseModel):
    recommendation: str   # STRONG_YES | YES | LEAN_YES | LEAN_NO | NO
    confidence: str       # HIGH | MEDIUM | LOW
    strengths: list[str]
    concerns: list[str]
    panelQuestions: list[str]


class _EvalResult(BaseModel):
    correctness: dict
    efficiency: dict
    followUp: dict
    summary: str
    hiring: Optional[dict] = None  # populated for B2B user_type only


class LLMEvaluator:
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.model = settings.openai_model
        if not self.client:
            logger.warning("OPENAI_API_KEY not set — AI evaluation will be skipped")

    def _filter_files(self, submission_files: Dict[str, str], blueprint: Dict[str, Any]) -> str:
        """Filter submission to only relevant files, capped at 50KB total."""
        repo_config = blueprint.get("repo", {})
        relevant_files = set(repo_config.get("relevantFiles", []))
        target_file = repo_config.get("targetFile")
        if target_file:
            relevant_files.add(target_file)

        filtered_data = {}
        total_chars = 0
        MAX_CHARS = 50_000

        for path in sorted(submission_files.keys()):
            if any(part in path.split("/") for part in ["node_modules", "dist", ".git", ".idea", "target", "build"]):
                continue
            if relevant_files and path not in relevant_files:
                continue
            content = submission_files[path]
            if len(content) > 20_000:
                continue
            if total_chars + len(content) > MAX_CHARS:
                logger.warning(f"Payload size limit reached, skipping files from {path}")
                break
            filtered_data[path] = content
            total_chars += len(content)

        return json.dumps(filtered_data, indent=2)

    def _build_system_prompt(
        self,
        blueprint: Dict[str, Any],
        follow_up_type: str,
        follow_up_instruction: str,
        user_type: str,
    ) -> str:
        repo = blueprint.get("repo", {})
        evaluation = blueprint.get("evaluation", {})
        gold_master = repo.get("goldMasterSource", {})
        signals = evaluation.get("senioritySignals", [])
        mistakes = evaluation.get("commonMistakes", [])
        rubric = evaluation.get("rubric", {})

        gold_master_section = ""
        if gold_master:
            gm_files = "\n\n".join(
                f"// {path}\n{content}" for path, content in gold_master.items()
            )
            gold_master_section = f"\nREFERENCE IMPLEMENTATION (gold master — do not reveal to student):\n{gm_files}\n"

        signals_section = ""
        if signals:
            signals_section = "\nSENIORITY SIGNALS TO CHECK:\n" + "\n".join(f"  • {s}" for s in signals) + "\n"

        mistakes_section = ""
        if mistakes:
            mistakes_section = "\nCOMMON MISTAKES AT THIS LEVEL:\n" + "\n".join(f"  • {m}" for m in mistakes) + "\n"

        rubric_section = ""
        if rubric:
            rubric_section = f"\nSCORING RUBRIC (anchor your scores to these):\n{json.dumps(rubric, indent=2)}\n"

        hiring_instruction = ""
        if user_type == "B2B":
            hiring_instruction = """
Also return a "hiring" key with:
{
  "recommendation": "STRONG_YES | YES | LEAN_YES | LEAN_NO | NO",
  "confidence": "HIGH | MEDIUM | LOW",
  "strengths": ["3-5 specific observations about what this candidate did well"],
  "concerns": ["3-5 specific gaps or risks a hiring manager should know"],
  "panelQuestions": ["2-3 follow-up questions to probe seniority depth"]
}"""

        return f"""You are a senior software engineering interviewer evaluating a candidate's code submission.

TASK DESCRIPTION: {blueprint.get('task', {}).get('description', 'N/A')}
CONSTRAINTS: {blueprint.get('task', {}).get('constraints', [])}
EXPECTED COMPLEXITY: {blueprint.get('task', {}).get('expectedComplexity', {})}
FOLLOW-UP CONTEXT: {blueprint.get('followUpContext', '')}
{gold_master_section}{signals_section}{mistakes_section}{rubric_section}
Evaluate the submission in three layers:
1. Correctness: Did they implement the required logic correctly? Score 0-10 using the rubric above.
2. Efficiency: Is the solution well-designed for scale and edge cases? Score 0-10 using the rubric above.
3. Interviewer Follow-up (type: {follow_up_type}):
   {follow_up_instruction}
{hiring_instruction}
Return a JSON object with exactly these keys (plus "hiring" if B2B):
{{
    "correctness": {{ "finding": "detailed finding comparing to gold master and seniority signals", "score": 0-10 }},
    "efficiency": {{ "finding": "detailed finding including code quality observations", "score": 0-10 }},
    "followUp": {{ "type": "{follow_up_type}", "content": "the follow-up question or coaching statement" }},
    "summary": "1-2 sentence overall summary for the candidate"
}}"""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _call_llm(self, system_prompt: str, user_content: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )
        usage = response.usage
        cached = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0)
        logger.info(
            f"[llm-eval] tokens — prompt: {usage.prompt_tokens}, "
            f"completion: {usage.completion_tokens}, cached: {cached}"
        )
        return response.choices[0].message.content

    def evaluate(
        self,
        blueprint: Dict[str, Any],
        submission_diff: str,
        test_results: str = "",
        remaining_time: int = 0,
        user_type: str = "B2C",
    ) -> Dict[str, Any]:
        """Evaluate a candidate's submission using GPT-4o mini.

        System prompt (static per challenge scenario) is reused across concurrent evaluations —
        OpenAI automatically caches matching prefixes > 1024 tokens (50% discount).
        goldMasterSource in the system prompt enables precise reference-based scoring.
        """
        if not self.client:
            return {"error": "OpenAI client not configured", "success": False, "summary": "AI evaluation unavailable."}

        logger.info(f"Starting LLM evaluation — user_type={user_type}, remaining={remaining_time}s, model={self.model}")

        follow_up_type = "IMPLEMENTATION" if remaining_time > 900 else "CONVERSATIONAL"

        if user_type == "B2B":
            follow_up_instruction = (
                "Focus on seniority signals: Does the candidate understand the trade-offs they made? "
                "Would you feel comfortable with this engineer owning this system in production? "
                "Frame follow-up as questions a hiring manager would ask to assess seniority level."
            )
        else:
            follow_up_instruction = (
                "Focus on coaching and blind spots: What did the candidate nearly get right? "
                "What concept or pattern are they missing? "
                "Frame follow-up to help them learn and improve."
            )

        system_prompt = self._build_system_prompt(blueprint, follow_up_type, follow_up_instruction, user_type)

        test_results_section = ""
        if test_results and test_results.strip():
            test_results_section = f"\nTEST RESULTS FROM GRADING PIPELINE:\n{test_results.strip()}\n"

        user_content = (
            f"BLUEPRINT CONTEXT:\n{json.dumps(blueprint, default=str)}\n\n"
            f"CANDIDATE SUBMISSION:\n{submission_diff}"
            f"{test_results_section}"
        )

        try:
            raw = self._call_llm(system_prompt, user_content)
            data = json.loads(raw)
            validated = _EvalResult.model_validate(data)
            result = validated.model_dump()
            # Validate B2B hiring assessment if present
            if user_type == "B2B" and "hiring" in data and data["hiring"]:
                try:
                    _HiringAssessment.model_validate(data["hiring"])
                    result["hiring"] = data["hiring"]
                except ValidationError as e:
                    logger.warning(f"B2B hiring assessment failed validation: {e}")
            return result
        except ValidationError as e:
            logger.warning(f"LLM response failed schema validation: {e}")
            return {
                "error": f"Response schema invalid: {e}",
                "success": False,
                "summary": "AI Evaluation returned an unexpected format.",
            }
        except Exception as e:
            logger.exception("LLM Evaluation failed")
            return {
                "error": str(e),
                "success": False,
                "summary": "AI Evaluation failed due to an internal error.",
            }
