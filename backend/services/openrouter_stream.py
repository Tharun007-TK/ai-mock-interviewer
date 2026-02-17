"""
OpenRouter Streaming Client — Token-by-token LLM responses.

Sends a chat completion request with stream=True and yields
each token as it arrives via SSE (Server-Sent Events).

Usage:
    async for token in stream_completion("Evaluate this answer..."):
        await ws.send_json({"type": "llm_token", "token": token})

TODO: Add support for streaming JSON and partial parsing.
"""

import json
import logging
import time
from typing import AsyncGenerator

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
STREAM_TIMEOUT = 45.0  # longer timeout for streaming


async def stream_completion(
    prompt: str,
    model: str | None = None,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> AsyncGenerator[str, None]:
    """
    Stream a chat completion from OpenRouter, yielding tokens as they arrive.

    Args:
        prompt: User message.
        model: Model identifier (falls back to OPENROUTER_MODEL_QUESTION).
        system_prompt: Optional system message.
        temperature: Sampling temperature.
        max_tokens: Max response tokens.

    Yields:
        Individual tokens/chunks as strings.

    Raises:
        RuntimeError: If API key missing or request fails.
    """
    settings = get_settings()

    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set in environment.")

    model = model or settings.OPENROUTER_MODEL_QUESTION

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "AI Mock Interviewer",
    }

    start = time.monotonic()
    first_token_time: float | None = None
    token_count = 0

    async with httpx.AsyncClient(timeout=STREAM_TIMEOUT) as client:
        async with client.stream(
            "POST",
            OPENROUTER_BASE_URL,
            json=body,
            headers=headers,
        ) as response:
            if response.status_code != 200:
                body_text = await response.aread()
                logger.error(f"OpenRouter stream error {response.status_code}: {body_text[:300]}")
                raise RuntimeError(f"OpenRouter stream error: {response.status_code}")

            # Parse SSE stream
            async for line in response.aiter_lines():
                if not line:
                    continue

                # SSE format: "data: {...}" or "data: [DONE]"
                if not line.startswith("data: "):
                    continue

                data_str = line[6:]  # strip "data: " prefix

                if data_str.strip() == "[DONE]":
                    break

                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")

                    if content:
                        if first_token_time is None:
                            first_token_time = time.monotonic()
                            ttft_ms = (first_token_time - start) * 1000
                            logger.info(f"OpenRouter TTFT: {ttft_ms:.0f}ms [{model}]")

                        token_count += 1
                        yield content

                except (json.JSONDecodeError, IndexError, KeyError):
                    continue

    total_ms = (time.monotonic() - start) * 1000
    logger.info(f"OpenRouter stream complete: {token_count} tokens in {total_ms:.0f}ms [{model}]")


async def stream_completion_full(
    prompt: str,
    model: str | None = None,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    """
    Convenience: stream a completion and return the full text.
    Useful when you want latency logging but don't need per-token forwarding.
    """
    chunks = []
    async for token in stream_completion(
        prompt=prompt,
        model=model,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    ):
        chunks.append(token)
    return "".join(chunks)
