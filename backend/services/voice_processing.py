"""
Voice Processing Service
- Accept audio bytes from the frontend
- Transcribe to text using Deepgram API
- Clean and validate transcript

TODO: Add streaming transcription for real-time feedback.
"""

import logging
import re

from services.deepgram_service import deepgram_service

logger = logging.getLogger(__name__)


class VoiceProcessingService:
    """Handles audio-to-text transcription via Deepgram."""

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        mimetype: str = "audio/webm",
    ) -> str:
        """
        Transcribe audio bytes to text using Deepgram.

        Args:
            audio_bytes: Raw audio data from browser MediaRecorder.
            mimetype: Audio format (default webm from browser).

        Returns:
            Cleaned transcript string.

        Raises:
            ValueError: If audio is too short or invalid.
            RuntimeError: If Deepgram API fails.
        """
        # Validate first
        if not await self.validate_audio(audio_bytes):
            raise ValueError("Audio data is too small or empty.")

        # Call Deepgram
        raw_transcript = await deepgram_service.transcribe(
            audio_bytes=audio_bytes,
            mimetype=mimetype,
        )

        # Clean up the transcript
        cleaned = self._clean_transcript(raw_transcript)

        if not cleaned:
            logger.warning("Deepgram returned empty transcript")
            raise ValueError("Could not transcribe audio. Please try again.")

        return cleaned

    async def validate_audio(self, audio_bytes: bytes) -> bool:
        """
        Validate audio format and size.

        TODO: Add format detection (webm, wav, mp3) and
              enforce max duration (~5 min per answer).
        """
        if not audio_bytes or len(audio_bytes) < 100:
            return False
        # ~10MB max (generous for a single answer recording)
        if len(audio_bytes) > 10 * 1024 * 1024:
            return False
        return True

    @staticmethod
    def _clean_transcript(text: str) -> str:
        """
        Clean up raw transcript from Deepgram.
        - Normalize whitespace
        - Remove filler artifacts
        """
        if not text:
            return ""

        # Collapse multiple spaces / newlines
        text = re.sub(r"\s+", " ", text).strip()

        return text


# Singleton instance
voice_processing_service = VoiceProcessingService()
