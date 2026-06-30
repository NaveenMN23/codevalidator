from __future__ import annotations
import json
from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError, InternalServerError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config.settings import settings
from infrastructure.logger import log

_TRANSIENT_ERRORS = (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)

_PRICE_PER_1M: dict[str, dict[str, float]] = {
    "gpt-4o":      {"input": 2.50,  "cached": 1.25,  "output": 10.00},
    "gpt-4o-mini": {"input": 0.15,  "cached": 0.075, "output": 0.60},
}

try:
    import tiktoken
    _enc = tiktoken.encoding_for_model("gpt-4o")
except Exception:
    _enc = None


def _count_tokens(text: str) -> int:
    if _enc is None:
        return len(text) // 4
    return len(_enc.encode(text))


class LLMClient:
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        if not self.client:
            log.warning("OPENAI_API_KEY not set — LLM calls will fail until configured")
        self._session_cost: float = 0.0

    def _log_usage(self, response, label: str) -> None:
        usage = response.usage
        cached = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0)
        non_cached = usage.prompt_tokens - cached
        prices = _PRICE_PER_1M.get(settings.openai_model, _PRICE_PER_1M["gpt-4o-mini"])
        cost = (
            non_cached / 1_000_000 * prices["input"]
            + cached / 1_000_000 * prices["cached"]
            + usage.completion_tokens / 1_000_000 * prices["output"]
        )
        self._session_cost += cost
        log.info(
            f"[{label}] tokens prompt={usage.prompt_tokens}(cached={cached}) "
            f"completion={usage.completion_tokens} cost=${cost:.4f} "
            f"session_total=${self._session_cost:.4f}"
        )

    def _repair(self, raw: str, label: str) -> str:
        """One repair re-ask when the model returns non-JSON."""
        if not self.client:
            raise RuntimeError("OpenAI client not initialized")
        log.warning(f"[{label}] JSON parse failed — attempting repair re-ask")
        response = self.client.chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            max_tokens=settings.openai_max_tokens,
            messages=[
                {"role": "user", "content": raw},
                {"role": "assistant", "content": "I need to provide valid JSON. Here it is:"},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type(_TRANSIENT_ERRORS),
        reraise=True,
    )
    def complete_json(
        self,
        system_prompt: str,
        user_message: str,
        label: str = "llm",
        max_tokens_override: int | None = None,
    ) -> dict:
        if not self.client:
            raise RuntimeError("OpenAI client not initialized — set OPENAI_API_KEY")
        max_tok = max_tokens_override or settings.openai_max_tokens
        response = self.client.chat.completions.create(
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            max_tokens=max_tok,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )
        self._log_usage(response, label)
        raw = response.choices[0].message.content
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            repaired = self._repair(raw, label)
            return json.loads(repaired)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type(_TRANSIENT_ERRORS),
        reraise=True,
    )
    def complete_json_cached(
        self,
        system_prompt: str,
        user_message: str,
        label: str = "llm",
        max_tokens_override: int | None = None,
    ) -> dict:
        """Use for CODE_SUBMISSION — large static prefix goes in system for OpenAI prefix caching."""
        if not self.client:
            raise RuntimeError("OpenAI client not initialized — set OPENAI_API_KEY")
        max_tok = max_tokens_override or settings.openai_max_tokens_code
        response = self.client.chat.completions.create(
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            max_tokens=max_tok,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )
        self._log_usage(response, label)
        raw = response.choices[0].message.content
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            repaired = self._repair(raw, label)
            return json.loads(repaired)


llm_client = LLMClient()
