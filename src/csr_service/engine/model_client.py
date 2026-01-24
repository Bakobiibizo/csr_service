"""
Async LLM client wrapper using the OpenAI SDK.

Connects to an Ollama instance (or any OpenAI-compatible endpoint) and
sends structured chat completions with JSON response format. Temperature
is set to 0.1 for reproducibility.
"""

from openai import AsyncOpenAI

from ..config import settings
from ..logging import logger
from ..schemas.response import Usage


class ModelClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.ollama_base_url,
            api_key=settings.model_api_key,
            timeout=settings.model_timeout,
        )
        self.model_id = settings.model_id

    async def generate(self, system_prompt: str, user_prompt: str) -> tuple[str, Usage]:
        try:
            kwargs: dict = {
                "model": self.model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": settings.model_temperature,
            }
            if settings.model_json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            usage = Usage()
            if response.usage:
                usage = Usage(
                    input_tokens=response.usage.prompt_tokens or 0,
                    output_tokens=response.usage.completion_tokens or 0,
                )
            return content, usage
        except Exception as e:
            logger.error(f"Model call failed: {e}")
            raise
