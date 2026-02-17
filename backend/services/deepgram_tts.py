"""
Deepgram TTS Service — Real-time text-to-speech via WebSocket.

Connects to Deepgram's streaming TTS API and converts text chunks
into audio frames that can be forwarded to the client in real time.

Usage:
    tts = DeepgramTTSClient(on_audio=my_callback)
    await tts.connect()
    await tts.send_text("Hello, great answer!")
    await tts.flush()   # get remaining audio
    await tts.close()

TODO: Add voice style customization (pitch, speed, emotion).
TODO: Add voice selection from .env (aura-2-helena-en, aura-2-orion-en, etc.).
"""

import asyncio
import base64
import json
import logging
import time

import websockets

from config import get_settings

logger = logging.getLogger(__name__)

DEEPGRAM_TTS_WS_URL = "wss://api.deepgram.com/v1/speak"

# Default voice — Deepgram Aura 2
# TODO: Make configurable via DEEPGRAM_TTS_VOICE env var
DEFAULT_VOICE = "aura-2-helena-en"
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_ENCODING = "linear16"


class DeepgramTTSClient:
    """
    Async WebSocket client for Deepgram streaming TTS.

    Sends text chunks, receives raw audio frames, and fires
    an async callback for each audio chunk received.

    Args:
        on_audio: Async callback(audio_bytes: bytes) fired for each audio frame.
        voice: Deepgram voice model name.
        sample_rate: Audio sample rate in Hz.
        encoding: Audio encoding format (linear16, mulaw, alaw, mp3, opus).
    """

    def __init__(
        self,
        on_audio,  # async callable(bytes) -> None
        voice: str = DEFAULT_VOICE,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        encoding: str = DEFAULT_ENCODING,
    ):
        self._on_audio = on_audio
        self._voice = voice
        self._sample_rate = sample_rate
        self._encoding = encoding
        self._ws = None
        self._receive_task: asyncio.Task | None = None
        self._connected = False
        self._start_time: float = 0
        self._audio_chunks_sent = 0

        # Event set when Deepgram sends a Flushed response
        self._flush_complete = asyncio.Event()

    async def connect(self) -> None:
        """Open WebSocket connection to Deepgram TTS."""
        settings = get_settings()
        if not settings.DEEPGRAM_API_KEY:
            raise RuntimeError("DEEPGRAM_API_KEY not set.")

        params = (
            f"?model={self._voice}"
            f"&sample_rate={self._sample_rate}"
            f"&encoding={self._encoding}"
        )

        url = DEEPGRAM_TTS_WS_URL + params

        extra_headers = {
            "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
        }

        self._start_time = time.monotonic()
        logger.info(f"Connecting to Deepgram TTS ({self._voice})...")

        self._ws = await websockets.connect(
            url,
            additional_headers=extra_headers,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        )
        self._connected = True

        # Start background receiver for audio frames
        self._receive_task = asyncio.create_task(self._receive_loop())

        latency_ms = (time.monotonic() - self._start_time) * 1000
        logger.info(f"Deepgram TTS connected in {latency_ms:.0f}ms")

    async def send_text(self, text: str) -> None:
        """Send a text chunk for synthesis. Deepgram buffers until flush."""
        if not self._ws or not self._connected:
            raise RuntimeError("TTS client not connected.")

        if not text.strip():
            return

        msg = {"type": "Speak", "text": text}
        await self._ws.send(json.dumps(msg))
        logger.debug(f"TTS text sent: {len(text)} chars")

    async def flush(self) -> None:
        """
        Flush the TTS buffer — tells Deepgram to synthesise all pending text
        and send the remaining audio. Waits for Flushed confirmation.
        """
        if not self._ws or not self._connected:
            return

        self._flush_complete.clear()
        await self._ws.send(json.dumps({"type": "Flush"}))

        # Wait up to 10s for Deepgram to confirm flush
        try:
            await asyncio.wait_for(self._flush_complete.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("TTS flush timed out after 10s")

    async def close(self) -> None:
        """Gracefully close the TTS WebSocket connection."""
        self._connected = False
        if self._ws:
            try:
                # Close message flushes remaining audio then closes
                await self._ws.send(json.dumps({"type": "Close"}))
                await asyncio.sleep(0.5)  # Allow final audio to arrive
            except Exception:
                pass
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        logger.info(f"Deepgram TTS closed ({self._audio_chunks_sent} audio chunks sent)")

    async def _receive_loop(self) -> None:
        """Background loop that receives audio frames and control messages."""
        try:
            async for message in self._ws:
                if not self._connected:
                    break

                if isinstance(message, bytes):
                    # Binary frame = audio data
                    self._audio_chunks_sent += 1
                    await self._on_audio(message)

                elif isinstance(message, str):
                    # JSON control message
                    try:
                        msg = json.loads(message)
                        msg_type = msg.get("type", "")

                        if msg_type == "Flushed":
                            self._flush_complete.set()
                            logger.debug("TTS flush confirmed")

                        elif msg_type == "Warning":
                            logger.warning(f"Deepgram TTS warning: {msg.get('description', msg)}")

                        elif msg_type == "Error":
                            logger.error(f"Deepgram TTS error: {msg.get('description', msg)}")

                        elif msg_type == "Metadata":
                            logger.debug(f"TTS metadata: request_id={msg.get('request_id', 'N/A')}")

                    except json.JSONDecodeError:
                        pass

        except websockets.ConnectionClosed as e:
            logger.info(f"TTS WS closed: code={e.code}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"TTS receive loop error: {e}")
        finally:
            self._connected = False


# ── Sentence Buffering Utility ──

class SentenceBuffer:
    """
    Accumulates streamed LLM tokens and yields complete sentences.
    Sentences are detected by punctuation boundaries (. ! ? : ;).

    Usage:
        buf = SentenceBuffer()
        for token in llm_stream:
            sentence = buf.add(token)
            if sentence:
                await tts.send_text(sentence)
        remainder = buf.drain()
        if remainder:
            await tts.send_text(remainder)
    """

    SENTENCE_ENDINGS = frozenset(".!?;:")

    def __init__(self, min_chars: int = 20):
        self._buffer: list[str] = []
        self._char_count = 0
        self._min_chars = min_chars  # Minimum chars before splitting

    def add(self, token: str) -> str | None:
        """
        Add a token. Returns a complete sentence if one is ready, else None.
        Waits for at least min_chars to avoid sending tiny fragments.
        """
        self._buffer.append(token)
        self._char_count += len(token)

        # Check if we have a sentence boundary
        if (
            self._char_count >= self._min_chars
            and token.rstrip()
            and token.rstrip()[-1] in self.SENTENCE_ENDINGS
        ):
            return self._flush_buffer()

        return None

    def drain(self) -> str:
        """Return any remaining text in the buffer."""
        return self._flush_buffer()

    def _flush_buffer(self) -> str:
        text = "".join(self._buffer).strip()
        self._buffer.clear()
        self._char_count = 0
        return text
