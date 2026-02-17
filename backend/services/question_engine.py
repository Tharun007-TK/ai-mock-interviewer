"""
Question Engine Service
- Generate adaptive interview questions via LLM (OpenRouter)
- Retrieve relevant questions from ChromaDB based on resume + JD
- Generate follow-up questions based on answer quality

TODO: Seed ChromaDB with a base question bank for retrieval.
"""

import json
import logging

from config import get_settings
from models.schemas import QuestionOut
from services.openrouter_client import generate_json_completion

logger = logging.getLogger(__name__)


# ── Default question bank (MVP fallback) ──
DEFAULT_QUESTIONS = [
    {
        "question_id": 1,
        "question_text": "Tell me about yourself and your background.",
        "category": "behavioral",
    },
    {
        "question_id": 2,
        "question_text": "What are your key technical skills and how have you applied them?",
        "category": "technical",
    },
    {
        "question_id": 3,
        "question_text": "Describe a challenging project you worked on. What was your role?",
        "category": "situational",
    },
    {
        "question_id": 4,
        "question_text": "How do you approach debugging a complex issue in production?",
        "category": "technical",
    },
    {
        "question_id": 5,
        "question_text": "Where do you see yourself in the next 2-3 years?",
        "category": "behavioral",
    },
    {
        "question_id": 6,
        "question_text": "Explain a concept from your field to someone non-technical.",
        "category": "technical",
    },
    {
        "question_id": 7,
        "question_text": "How do you handle tight deadlines and multiple priorities?",
        "category": "behavioral",
    },
    {
        "question_id": 8,
        "question_text": "Describe a time when you had a disagreement with a team member. How did you resolve it?",
        "category": "situational",
    },
    {
        "question_id": 9,
        "question_text": "What motivates you to apply for this role?",
        "category": "behavioral",
    },
    {
        "question_id": 10,
        "question_text": "Do you have any questions for us?",
        "category": "behavioral",
    },
]


# ── LLM Prompts ──

QUESTION_GEN_SYSTEM = """You are an expert technical interviewer. Generate interview questions tailored to the candidate's resume and the target job description.

Return ONLY valid JSON — an array of question objects:
[
  {"question_text": "...", "category": "technical|behavioral|situational"},
  ...
]

Rules:
- Generate a mix: ~40% technical, ~30% behavioral, ~30% situational
- Questions should be specific to the resume skills and job requirements
- Avoid generic questions — reference actual skills/experience from the resume
- Order from introductory to advanced
- Do NOT number the questions in the text"""

FOLLOW_UP_SYSTEM = """You are an expert interviewer generating a follow-up question.

Based on the original question, the candidate's answer, and the evaluation score,
generate ONE follow-up question that probes deeper into the topic.

Return ONLY valid JSON:
{"question_text": "...", "category": "technical|behavioral|situational"}"""


class QuestionEngineService:
    """Generates and retrieves interview questions."""

    async def generate_questions(
        self,
        resume_data: dict,
        job_description: str,
        num_questions: int = 10,
    ) -> list[dict]:
        """
        Generate a set of interview questions tailored to resume + JD.

        Uses LLM via OpenRouter to create personalized questions.
        Falls back to default question bank if LLM is unavailable.
        """
        settings = get_settings()

        if not settings.OPENROUTER_API_KEY:
            logger.info("OPENROUTER_API_KEY not set — using default questions")
            return DEFAULT_QUESTIONS[:num_questions]

        skills = resume_data.get("skills", [])
        experience = resume_data.get("experience", [])
        summary = resume_data.get("summary", "")

        prompt = f"""Generate {num_questions} interview questions for this candidate.

Candidate Resume:
- Skills: {', '.join(skills[:20]) if skills else 'Not provided'}
- Recent Experience: {json.dumps(experience[:3]) if experience else 'Not provided'}
- Summary: {summary[:300] if summary else 'Not provided'}

Job Description:
{job_description[:1500]}

Generate {num_questions} questions as a JSON array."""

        try:
            data = await generate_json_completion(
                prompt=prompt,
                system_prompt=QUESTION_GEN_SYSTEM,
                model=settings.OPENROUTER_MODEL_QUESTION,
                temperature=0.7,
                max_tokens=3000,
            )

            # Handle both direct array and wrapped {"questions": [...]} formats
            questions_list = data if isinstance(data, list) else data.get("questions", [])

            if not questions_list:
                logger.warning("LLM returned empty questions, using defaults")
                return DEFAULT_QUESTIONS[:num_questions]

            # Normalize into our expected format
            result = []
            for idx, q in enumerate(questions_list[:num_questions]):
                result.append({
                    "question_id": idx + 1,
                    "question_text": q.get("question_text", q.get("text", "")),
                    "category": q.get("category", "general"),
                })

            logger.info(f"Generated {len(result)} questions via LLM")
            return result

        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            logger.info("Falling back to default questions")
            return DEFAULT_QUESTIONS[:num_questions]

    async def generate_follow_up(
        self,
        original_question: str,
        user_answer: str,
        score: dict,
    ) -> QuestionOut | None:
        """
        Generate an adaptive follow-up question based on the user's answer.
        Returns None if LLM is unavailable or generation fails.
        """
        settings = get_settings()

        if not settings.OPENROUTER_API_KEY:
            return None

        prompt = f"""Original question: {original_question}
Candidate's answer: {user_answer[:500]}
Evaluation: {json.dumps(score)}

Generate a follow-up question that probes deeper."""

        try:
            data = await generate_json_completion(
                prompt=prompt,
                system_prompt=FOLLOW_UP_SYSTEM,
                model=settings.OPENROUTER_MODEL_QUESTION,
                temperature=0.6,
                max_tokens=300,
            )

            return QuestionOut(
                question_id=-1,  # follow-up marker
                question_text=data.get("question_text", ""),
                category=data.get("category", "technical"),
            )

        except Exception as e:
            logger.warning(f"Follow-up generation failed: {e}")
            return None

    async def get_next_question(
        self, questions: list[dict], current_index: int
    ) -> QuestionOut | None:
        """Get the next question from the list, or None if interview is complete."""
        if current_index >= len(questions):
            return None
        q = questions[current_index]
        return QuestionOut(
            question_id=q["question_id"],
            question_text=q["question_text"],
            category=q.get("category", ""),
        )


# Singleton instance
question_engine_service = QuestionEngineService()
