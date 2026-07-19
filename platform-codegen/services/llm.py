from pathlib import Path
from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError, InternalServerError
from config.settings import settings
from infrastructure.logger import log
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

_TRANSIENT_ERRORS = (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_MAX_INPUT_TOKENS = 100_000  # warn at 80% of GPT-4o 128K input window

_PRICE_PER_1M: dict[str, dict[str, float]] = {
    "gpt-4o":             {"input": 2.50,  "cached": 1.25,  "output": 10.00},
    "gpt-4o-mini":        {"input": 0.15,  "cached": 0.075, "output": 0.60},
    "gpt-4o-2024-11-20":  {"input": 2.50,  "cached": 1.25,  "output": 10.00},
}

try:
    import tiktoken
    _enc = tiktoken.encoding_for_model("gpt-4o")
except Exception:
    _enc = None


def _count_tokens(text: str) -> int:
    if _enc is None:
        return len(text) // 4  # rough fallback: ~4 chars per token
    return len(_enc.encode(text))


class LLMClient:
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        if not self.client:
            log.warning("OPENAI_API_KEY not set — LLM calls will fail until configured")
        self._session_cost: float = 0.0
        self._session_tokens: dict[str, int] = {"input": 0, "cached": 0, "output": 0}

    def load_prompt(self, name: str) -> str:
        """Load the body of a .mdx prompt file, stripping YAML frontmatter."""
        path = PROMPTS_DIR / f"{name}.mdx"
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        content = path.read_text(encoding="utf-8")
        if content.startswith("---"):
            end = content.index("---", 3)
            content = content[end + 3:].strip()
        return content

    def _warn_token_budget(self, system_prompt: str, user_message: str, label: str, max_tokens: int = 0) -> None:
        """Log the estimated input size, warn if it's eating into GPT-4o's 128K context
        window, and — separately — refuse to even attempt a call whose (prompt +
        requested completion) already exceeds this account's real per-minute rate limit.

        That second case is NOT a transient "too busy right now" 429 (`RateLimitError`,
        already retried elsewhere via `tenacity`) — it's a request that is mathematically
        too big to ever succeed, no matter how many times or how long it's retried, since
        its own size already exceeds the account's entire per-minute budget. Raising a
        plain `RuntimeError` here (not one of `_TRANSIENT_ERRORS`) means `tenacity`'s
        `retry_if_exception_type` correctly does NOT retry it — failing in under a second
        with a clear cause, instead of burning up to ~5 minutes of exponential backoff
        only to re-raise the same opaque OpenAI 429 at the end.
        """
        total = _count_tokens(system_prompt) + _count_tokens(user_message)
        log.info(f"[{label}] estimated input tokens: {total}")
        if total > _MAX_INPUT_TOKENS * 0.8:
            log.warning(f"[{label}] input is at {total / _MAX_INPUT_TOKENS:.0%} of token budget — consider pruning context")
        projected = total + max_tokens
        if max_tokens and projected > settings.openai_tpm_limit:
            raise RuntimeError(
                f"[{label}] request too large for this account's rate limit: "
                f"~{total} prompt tokens + {max_tokens} reserved output tokens = "
                f"~{projected}, over the configured openai_tpm_limit of "
                f"{settings.openai_tpm_limit}. Reduce the prompt context or "
                f"max_tokens_override for this call rather than retrying — a request "
                f"this size cannot succeed against this account's TPM cap regardless "
                f"of retries."
            )

    def reset_session_cost(self) -> None:
        self._session_cost = 0.0
        self._session_tokens = {"input": 0, "cached": 0, "output": 0}

    def _log_usage(self, response, label: str) -> None:
        usage = response.usage
        cached = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0)
        non_cached_input = usage.prompt_tokens - cached

        prices = _PRICE_PER_1M.get(settings.openai_model, _PRICE_PER_1M["gpt-4o"])
        call_cost = (
            non_cached_input / 1_000_000 * prices["input"]
            + cached / 1_000_000 * prices["cached"]
            + usage.completion_tokens / 1_000_000 * prices["output"]
        )
        self._session_cost += call_cost
        self._session_tokens["input"] += non_cached_input
        self._session_tokens["cached"] += cached
        self._session_tokens["output"] += usage.completion_tokens

        log.info(
            f"[{label}] tokens — prompt: {usage.prompt_tokens} "
            f"(cached: {cached}), completion: {usage.completion_tokens}, "
            f"total: {usage.total_tokens} | "
            f"cost: ${call_cost:.4f} (session total: ${self._session_cost:.4f})"
        )

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type(_TRANSIENT_ERRORS),
        reraise=True,
    )
    def complete_json(
        self,
        system_prompt: str,
        user_message: str,
        label: str = "llm",
        max_tokens_override: int | None = None,
    ) -> str:
        """Call GPT with JSON output mode. Retries up to 3 times with exponential backoff."""
        if not self.client:
            raise RuntimeError("OpenAI client not initialized — set OPENAI_API_KEY")
        max_tok = max_tokens_override or settings.openai_max_tokens
        self._warn_token_budget(system_prompt, user_message, label, max_tokens=max_tok)
        if max_tokens_override:
            log.info(f"[{label}] using max_tokens_override={max_tokens_override}")
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
        return response.choices[0].message.content

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type(_TRANSIENT_ERRORS),
        reraise=True,
    )
    def complete_json_cached(
        self,
        system_prompt: str,
        user_message: str,
        label: str = "llm",
        max_tokens_override: int | None = None,
    ) -> str:
        """Like complete_json but structured for OpenAI prefix caching.

        Put static/large content in system_prompt, dynamic/tiny content in user_message.
        OpenAI automatically caches prefixes > 1024 tokens; cached tokens cost 50% less.
        Cache hit rate is visible in the logged 'cached' token count.
        """
        if not self.client:
            raise RuntimeError("OpenAI client not initialized — set OPENAI_API_KEY")
        max_tok = max_tokens_override or settings.openai_max_tokens
        self._warn_token_budget(system_prompt, user_message, label, max_tokens=max_tok)
        if max_tokens_override:
            log.info(f"[{label}] using max_tokens_override={max_tokens_override}")
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
        return response.choices[0].message.content

    @retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type(_TRANSIENT_ERRORS),
        reraise=True,
    )
    def complete_json_with_messages(
        self,
        messages: list[dict],
        label: str = "llm",
        max_tokens_override: int | None = None,
    ) -> str:
        """Multi-turn call for cache-optimised sequences.

        Caller controls the full messages array (system + any prior turns + user).
        """
        if not self.client:
            raise RuntimeError("OpenAI client not initialized — set OPENAI_API_KEY")
        system_text = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_text = next((m["content"] for m in messages if m["role"] == "user"), "")
        max_tok = max_tokens_override or settings.openai_max_tokens
        self._warn_token_budget(system_text, user_text, label, max_tokens=max_tok)
        response = self.client.chat.completions.create(
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            max_tokens=max_tok,
            messages=messages,
            response_format={"type": "json_object"},
        )
        self._log_usage(response, label)
        return response.choices[0].message.content


llm_client = LLMClient()
