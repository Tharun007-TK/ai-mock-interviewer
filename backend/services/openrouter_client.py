"""
OpenRouter Client — Unified LLM gateway.

Routes all LLM calls through OpenRouter (https://openrouter.ai/api/v1),
which supports OpenAI, Llama 3, Claude, Gemini, and 200+ models via
a single API key and OpenAI-compatible format.

Usage:
    from services.openrouter_client import generate_completion
    result = await generate_completion("Summarise this text...", model="openai/gpt-4o-mini")

TODO: Add streaming support for real-time question delivery.
"""

import json
import logging
import re

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
REQUEST_TIMEOUT = 30.0  # seconds


async def generate_completion(
    prompt: str,
    model: str | None = None,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 2000,
    json_mode: bool = False,
) -> str:
    """
    Send a chat completion request to OpenRouter.

    Args:
        prompt: User message content.
        model: Model identifier (e.g. "meta-llama/llama-3-8b-instruct").
                Falls back to OPENROUTER_MODEL_QUESTION from settings.
        system_prompt: Optional system message.
        temperature: Sampling temperature (0.0–2.0).
        max_tokens: Maximum response tokens.
        json_mode: If True, request JSON-only output.

    Returns:
        The assistant's response text.

    Raises:
        RuntimeError: If API call fails after retries or key is missing.
    """
    settings = get_settings()

    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set in environment.")

    model = model or settings.OPENROUTER_MODEL_QUESTION

    # Build messages
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # Build request body
    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode:
        body["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "AI Mock Interviewer",
    }

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            response = await client.post(
                OPENROUTER_BASE_URL,
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            logger.debug(f"OpenRouter [{model}]: {len(content)} chars returned")
            return content.strip()

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter HTTP error {e.response.status_code}: {e.response.text}")
            raise RuntimeError(f"OpenRouter API error: {e.response.status_code}") from e
        except httpx.TimeoutException:
            logger.error(f"OpenRouter request timed out after {REQUEST_TIMEOUT}s")
            raise RuntimeError("OpenRouter request timed out") from None
        except Exception as e:
            logger.error(f"OpenRouter call failed: {e}")
            raise RuntimeError(f"OpenRouter call failed: {e}") from e


async def generate_json_completion(
    prompt: str,
    model: str | None = None,
    system_prompt: str = "",
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> dict:
    """
    Convenience wrapper that requests JSON mode and parses the response.

    Returns:
        Parsed JSON dict.

    Raises:
        ValueError: If response is not valid JSON.
        RuntimeError: If API call fails.
    """
    content = await generate_completion(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
    )

    # Strip markdown code fences if the model wraps its output
    content = re.sub(r"^```(?:json)?\s*\n?", "", content)
    content = re.sub(r"\n?```\s*$", "", content)
    content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"OpenRouter returned invalid JSON: {content[:200]}")
        raise ValueError(f"Invalid JSON from LLM: {e}") from e
