"""OpenAI gpt-4o provider for the LLM extractor."""

import logging

from openai import AsyncOpenAI

from backend.config import settings

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o"
_COST_PER_INPUT_TOKEN = 5.0 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 15.0 / 1_000_000


class OpenAIProvider:
    """Calls OpenAI gpt-4o to produce a JSON extraction from a prompt.

    Args:
        model:      OpenAI model ID (default gpt-4o).
        max_tokens: Maximum completion tokens (default 2048).
    """

    def __init__(self, model: str = _MODEL, max_tokens: int = 2048) -> None:
        self.model = model
        self._max_tokens = max_tokens
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def complete(self, system_prompt: str, user_prompt: str) -> tuple[str, int, int, float]:
        """Send a chat completion request and return the raw JSON string + usage.

        Args:
            system_prompt: Instructions for the model.
            user_prompt:   The page content and extraction request.

        Returns:
            Tuple of (raw_json_string, tokens_in, tokens_out, usd_cost).

        Raises:
            Exception: Any OpenAI API error propagates to the caller.
        """
        response = await self._client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self._max_tokens,
            temperature=0.0,
        )
        usage = response.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        cost = tokens_in * _COST_PER_INPUT_TOKEN + tokens_out * _COST_PER_OUTPUT_TOKEN
        raw = response.choices[0].message.content or "{}"
        return raw, tokens_in, tokens_out, cost
