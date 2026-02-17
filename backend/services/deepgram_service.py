"""
Deepgram Service — Speech-to-text via Deepgram REST API.

Replaces Whisper for audio transcription. Uses the pre-recorded (batch)
endpoint — no SDK required, just httpx.

Usage:
    from services.deepgram_service import deepgram_service
    transcript = await deepgram_service.transcribe(audio_bytes)

TODO: Add streaming support for real-time transcription during interviews.
"""

import logging

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"
REQUEST_TIMEOUT = 60.0  # audio files can take longer


class DeepgramService:
    """Handles audio transcription via Deepgram REST API."""

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.DEEPGRAM_API_KEY

    async def transcribe(
        self,
        audio_bytes: bytes,
        mimetype: str = "audio/webm",
        language: str = "en",
    ) -> str:
        """
        Transcribe audio bytes using Deepgram's pre-recorded API.

        Args:
            audio_bytes: Raw audio data.
            mimetype: Audio MIME type (webm, wav, mp3, etc.).
            language: Language code for transcription.

        Returns:
            Clean transcript string.

        Raises:
            RuntimeError: If API key is missing or request fails.
        """
        if not self._api_key:
            raise RuntimeError(
                "DEEPGRAM_API_KEY not set. Add it to your .env file."
            )

        if not audio_bytes or len(audio_bytes) < 100:
            raise ValueError("Audio data is too small or empty.")

        # Query params for transcription options
        params = {
            "model": "nova-2",       # Deepgram's latest, most accurate model
            "language": language,
            "smart_format": "true",   # Punctuation + formatting
            "utterances": "false",
            "diarize": "false",
        }

        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": mimetype,
        }

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            try:
                response = await client.post(
                    DEEPGRAM_API_URL,
                    content=audio_bytes,
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                # Extract transcript from Deepgram response
                transcript = self._extract_transcript(data)
                logger.info(f"Deepgram transcription: {len(transcript)} chars")
                return transcript

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Deepgram HTTP error {e.response.status_code}: "
                    f"{e.response.text[:200]}"
                )
                raise RuntimeError(
                    f"Deepgram API error: {e.response.status_code}"
                ) from e
            except httpx.TimeoutException:
                logger.error(
                    f"Deepgram request timed out after {REQUEST_TIMEOUT}s"
                )
                raise RuntimeError("Deepgram transcription timed out") from None
            except Exception as e:
                logger.error(f"Deepgram call failed: {e}")
                raise RuntimeError(f"Deepgram transcription failed: {e}") from e

    @staticmethod
    def _extract_transcript(data: dict) -> str:
        """
        Pull the transcript string out of Deepgram's response JSON.

        Response shape:
        {
          "results": {
            "channels": [{
              "alternatives": [{
                "transcript": "the actual text..."
              }]
            }]
          }
        }
        """
        try:
            channels = data["results"]["channels"]
            if not channels:
                return ""
            alternatives = channels[0].get("alternatives", [])
            if not alternatives:
                return ""
            return alternatives[0].get("transcript", "").strip()
        except (KeyError, IndexError) as e:
            logger.warning(f"Unexpected Deepgram response structure: {e}")
            return ""


# Singleton
deepgram_service = DeepgramService()
