"""
Deepgram Live Transcription — WebSocket streaming client.

Connects to Deepgram's live transcription WebSocket API and streams
audio chunks for real-time speech-to-text.

Usage:
    client = DeepgramLiveClient(on_transcript=my_callback)
    await client.connect()
    await client.send(audio_chunk)
    await client.close()

TODO: Add automatic reconnection on transient failures.
TODO: Add TTS integration point for synthesised AI responses.
"""

import asyncio
import json
import logging
import time

import websockets

from config import get_settings

logger = logging.getLogger(__name__)

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


class TranscriptResult:
    """Parsed transcript result from Deepgram."""

    __slots__ = ("transcript", "is_final", "speech_final", "confidence", "duration")

    def __init__(self, transcript: str, is_final: bool, speech_final: bool,
                 confidence: float, duration: float):
        self.transcript = transcript
        self.is_final = is_final
        self.speech_final = speech_final
        self.confidence = confidence
        self.duration = duration

    def __repr__(self):
        tag = "FINAL" if self.is_final else "partial"
        return f"<Transcript [{tag}] {self.transcript[:50]!r}>"


class DeepgramLiveClient:
    """
    Async WebSocket client for Deepgram live transcription.

    Args:
        on_transcript: Async callback fired for each transcript result.
        model: Deepgram model name.
        language: Language code.
        sample_rate: Audio sample rate in Hz.
        encoding: Audio encoding (linear16/opus/etc).
    """

    def __init__(
        self,
        on_transcript,  # async callable(TranscriptResult) -> None
        model: str = "nova-2",
        language: str = "en",
        sample_rate: int = 16000,
        encoding: str = "linear16",
    ):
        self._on_transcript = on_transcript
        self._model = model
        self._language = language
        self._sample_rate = sample_rate
        self._encoding = encoding
        self._ws = None
        self._receive_task: asyncio.Task | None = None
        self._connected = False
        self._start_time: float = 0

    async def connect(self) -> None:
        """Open WebSocket connection to Deepgram."""
        settings = get_settings()
        if not settings.DEEPGRAM_API_KEY:
            raise RuntimeError("DEEPGRAM_API_KEY not set.")

        params = (
            f"?model={self._model}"
            f"&language={self._language}"
            f"&sample_rate={self._sample_rate}"
            f"&encoding={self._encoding}"
            f"&smart_format=true"
            f"&interim_results=true"
            f"&utterance_end_ms=1500"
            f"&vad_events=true"
            f"&endpointing=300"
        )

        url = DEEPGRAM_WS_URL + params

        extra_headers = {
            "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
        }

        self._start_time = time.monotonic()
        logger.info("Connecting to Deepgram live transcription...")

        self._ws = await websockets.connect(
            url,
            additional_headers=extra_headers,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        )
        self._connected = True

        # Start background receiver
        self._receive_task = asyncio.create_task(self._receive_loop())

        latency_ms = (time.monotonic() - self._start_time) * 1000
        logger.info(f"Deepgram WS connected in {latency_ms:.0f}ms")

    async def send(self, audio_bytes: bytes) -> None:
        """Send an audio chunk to Deepgram for transcription."""
        if not self._ws or not self._connected:
            raise RuntimeError("Deepgram client not connected.")
        await self._ws.send(audio_bytes)

    async def close(self) -> None:
        """Gracefully close the Deepgram connection."""
        self._connected = False
        if self._ws:
            try:
                # Send CloseStream message per Deepgram protocol
                await self._ws.send(json.dumps({"type": "CloseStream"}))
                await asyncio.sleep(0.3)  # Allow final results to arrive
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

        logger.info("Deepgram WS connection closed")

    async def _receive_loop(self) -> None:
        """Background loop that reads messages from Deepgram and fires callbacks."""
        try:
            async for raw_message in self._ws:
                if not self._connected:
                    break

                try:
                    msg = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type", "")

                if msg_type == "Results":
                    result = self._parse_result(msg)
                    if result and result.transcript:
                        await self._on_transcript(result)

                elif msg_type == "UtteranceEnd":
                    # Deepgram detected end of utterance (silence)
                    # Fire a special "speech_final" result
                    await self._on_transcript(TranscriptResult(
                        transcript="",
                        is_final=True,
                        speech_final=True,
                        confidence=1.0,
                        duration=0.0,
                    ))

                elif msg_type == "Metadata":
                    logger.debug(f"Deepgram metadata: {msg.get('request_id', 'N/A')}")

                elif msg_type == "Error":
                    logger.error(f"Deepgram error: {msg.get('description', msg)}")

        except websockets.ConnectionClosed as e:
            logger.info(f"Deepgram WS closed: code={e.code} reason={e.reason}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Deepgram receive loop error: {e}")
        finally:
            self._connected = False

    @staticmethod
    def _parse_result(msg: dict) -> TranscriptResult | None:
        """Parse a Deepgram Results message into a TranscriptResult."""
        try:
            channel = msg["channel"]
            alt = channel["alternatives"][0]
            return TranscriptResult(
                transcript=alt.get("transcript", "").strip(),
                is_final=msg.get("is_final", False),
                speech_final=msg.get("speech_final", False),
                confidence=alt.get("confidence", 0.0),
                duration=msg.get("duration", 0.0),
            )
        except (KeyError, IndexError):
            return None
