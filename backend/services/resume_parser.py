"""
Resume Parser Service
- Extract raw text from PDF uploads (pdfplumber, PyPDF2 fallback)
- Call LLM via OpenRouter for structured JSON extraction
- Validate output with Pydantic ParsedResume model
- Retry once if JSON is invalid
"""

import io
import json
import logging
import re

from config import get_settings
from models.schemas import ParsedResume
from services.openrouter_client import generate_json_completion

logger = logging.getLogger(__name__)

# ── LLM prompt ──

SYSTEM_PROMPT = """You are an expert resume parser. Given raw text extracted from a resume PDF, extract structured data and return ONLY valid JSON. No markdown, no explanation — just the JSON object.

Required JSON schema:
{
  "name": "string",
  "email": "string",
  "phone": "string",
  "skills": ["string"],
  "experience": [
    {
      "title": "string",
      "company": "string",
      "duration": "string",
      "description": "string"
    }
  ],
  "education": [
    {
      "degree": "string",
      "institution": "string",
      "year": "string"
    }
  ],
  "summary": "A 2-3 sentence professional summary"
}

Rules:
- Extract ALL skills mentioned, including tools, languages, and frameworks.
- If a field cannot be determined, use empty string or empty array.
- Phone should include country code if present.
- Experience entries should be ordered most recent first.
- Return ONLY the JSON object, no wrapping text."""


class ResumeParserService:
    """Handles PDF parsing and LLM-based resume structuring."""

    # ────────────────────────────────────────
    # PDF Text Extraction
    # ────────────────────────────────────────

    async def parse_pdf(self, file_bytes: bytes) -> str:
        """
        Extract raw text from PDF bytes.
        Tries pdfplumber first (better layout handling), falls back to PyPDF2.
        """
        text = await self._extract_with_pdfplumber(file_bytes)
        if not text:
            text = await self._extract_with_pypdf2(file_bytes)
        if not text:
            raise ValueError("Could not extract any text from the PDF. Is it a scanned image?")
        return text

    async def _extract_with_pdfplumber(self, file_bytes: bytes) -> str:
        """Primary extractor — pdfplumber handles complex layouts better."""
        try:
            import pdfplumber

            text_parts = []
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return "\n".join(text_parts).strip()
        except ImportError:
            logger.info("pdfplumber not installed, falling back to PyPDF2")
            return ""
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")
            return ""

    async def _extract_with_pypdf2(self, file_bytes: bytes) -> str:
        """Fallback extractor — PyPDF2."""
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(io.BytesIO(file_bytes))
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n".join(text_parts).strip()
        except Exception as e:
            logger.warning(f"PyPDF2 extraction failed: {e}")
            return ""

    # ────────────────────────────────────────
    # LLM Structuring (via OpenRouter)
    # ────────────────────────────────────────

    async def structure_resume(self, raw_text: str) -> ParsedResume:
        """
        Call LLM via OpenRouter to convert raw resume text into structured ParsedResume.
        Retries once if the response isn't valid JSON.
        Falls back to basic extraction if LLM is unavailable.
        """
        settings = get_settings()
        if not settings.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY not set — using basic extraction fallback")
            return self._fallback_parse(raw_text)

        # Attempt 1
        parsed = await self._call_llm(raw_text)
        if parsed:
            return parsed

        # Retry once
        logger.info("First LLM attempt returned invalid JSON, retrying...")
        parsed = await self._call_llm(raw_text, retry=True)
        if parsed:
            return parsed

        # Both attempts failed — use fallback
        logger.warning("LLM structuring failed after retry, using fallback")
        return self._fallback_parse(raw_text)

    async def _call_llm(self, raw_text: str, retry: bool = False) -> ParsedResume | None:
        """
        Single LLM call via OpenRouter. Returns ParsedResume or None if response can't be parsed.
        """
        prompt = f"Parse this resume:\n\n{raw_text[:6000]}"
        if retry:
            prompt += "\n\nIMPORTANT: Return ONLY the JSON object, no markdown fences or extra text."

        try:
            data = await generate_json_completion(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                model=get_settings().OPENROUTER_MODEL_QUESTION,
                temperature=0.1,
                max_tokens=2000,
            )
            return ParsedResume(**data)

        except ValueError as e:
            logger.warning(f"LLM returned invalid JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    # ────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────

    @staticmethod
    def _fallback_parse(raw_text: str) -> ParsedResume:
        """
        Basic regex extraction when LLM is unavailable.
        Extracts email and phone from text, puts everything else in summary.
        """
        email = ""
        phone = ""

        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw_text)
        if email_match:
            email = email_match.group(0)

        phone_match = re.search(r"[\+]?[\d\s\-\(\)]{7,15}", raw_text)
        if phone_match:
            phone = phone_match.group(0).strip()

        return ParsedResume(
            name="",
            email=email,
            phone=phone,
            skills=[],
            experience=[],
            education=[],
            summary=raw_text[:500] if raw_text else "",
        )

    # ────────────────────────────────────────
    # Public Pipeline
    # ────────────────────────────────────────

    async def parse_and_structure(self, file_bytes: bytes) -> ParsedResume:
        """Full pipeline: PDF bytes → raw text → LLM → validated ParsedResume."""
        raw_text = await self.parse_pdf(file_bytes)
        return await self.structure_resume(raw_text)


# Singleton
resume_parser_service = ResumeParserService()
