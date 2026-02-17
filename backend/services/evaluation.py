"""
Evaluation Engine Service
- Rubric-based structured scoring of interview answers
- Uses LLM via OpenRouter for intelligent evaluation
- Outputs JSON scores per answer
"""

import logging

from config import get_settings
from models.schemas import AnswerScore
from services.openrouter_client import generate_json_completion

logger = logging.getLogger(__name__)

# ── Evaluation prompt ──

EVAL_SYSTEM_PROMPT = """You are an expert technical interviewer evaluating a candidate's answer.

Score the answer on these dimensions (0.0–10.0):
- relevance: How relevant is the answer to the question?
- clarity: How clearly is the answer communicated?
- depth: How thorough and detailed is the answer?
- overall: Holistic assessment

Also provide brief, constructive feedback (2-3 sentences).

Return ONLY valid JSON:
{"relevance": X.X, "clarity": X.X, "depth": X.X, "overall": X.X, "feedback": "..."}

Be fair but critical. Score realistically — don't inflate scores."""


class EvaluationEngineService:
    """Evaluates interview answers against a structured rubric."""

    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        job_description: str = "",
        resume_data: dict | None = None,
    ) -> AnswerScore:
        """
        Evaluate a single answer using a structured rubric via LLM.

        Falls back to neutral scores if LLM is unavailable.
        """
        settings = get_settings()

        if not settings.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY not set — returning placeholder scores")
            return AnswerScore(
                relevance=5.0, clarity=5.0, depth=5.0, overall=5.0,
                feedback="[Placeholder] Evaluation requires OPENROUTER_API_KEY.",
            )

        prompt = f"""Evaluate this interview answer.

Question: {question}
Answer: {answer}
Job Description: {job_description[:1000] if job_description else 'N/A'}

Score on: relevance, clarity, depth, overall (0-10 each).
Include brief feedback."""

        try:
            data = await generate_json_completion(
                prompt=prompt,
                system_prompt=EVAL_SYSTEM_PROMPT,
                model=settings.OPENROUTER_MODEL_EVALUATION,
                temperature=0.2,
                max_tokens=500,
            )
            return AnswerScore(**data)

        except (ValueError, TypeError) as e:
            logger.warning(f"Evaluation LLM returned invalid data: {e}")
            return AnswerScore(
                relevance=5.0, clarity=5.0, depth=5.0, overall=5.0,
                feedback="Evaluation failed — using neutral scores.",
            )
        except Exception as e:
            logger.error(f"Evaluation LLM call failed: {e}")
            return AnswerScore(
                relevance=5.0, clarity=5.0, depth=5.0, overall=5.0,
                feedback="Evaluation failed — using neutral scores.",
            )

    async def should_follow_up(self, score: AnswerScore) -> bool:
        """
        Determine if a follow-up question should be asked based on the score.

        TODO: Implement adaptive logic using LLM:
              - Low depth → ask for more detail
              - Low relevance → re-ask or redirect
              - High score → move to next topic
        """
        return score.overall < 4.0

    async def aggregate_scores(self, scores: list[AnswerScore]) -> dict:
        """
        Aggregate all answer scores into a session summary.
        Returns overall averages and identifies strengths/improvements.
        """
        if not scores:
            return {
                "overall_score": 0.0,
                "avg_relevance": 0.0,
                "avg_clarity": 0.0,
                "avg_depth": 0.0,
                "strengths": [],
                "improvements": [],
            }

        avg_relevance = sum(s.relevance for s in scores) / len(scores)
        avg_clarity = sum(s.clarity for s in scores) / len(scores)
        avg_depth = sum(s.depth for s in scores) / len(scores)
        avg_overall = sum(s.overall for s in scores) / len(scores)

        strengths = []
        improvements = []

        if avg_relevance >= 7.0:
            strengths.append("Strong relevance in answers")
        elif avg_relevance < 5.0:
            improvements.append("Improve answer relevance to questions asked")

        if avg_clarity >= 7.0:
            strengths.append("Clear and articulate communication")
        elif avg_clarity < 5.0:
            improvements.append("Work on clarity and structure of responses")

        if avg_depth >= 7.0:
            strengths.append("Detailed and thorough responses")
        elif avg_depth < 5.0:
            improvements.append("Provide more depth and specific examples")

        return {
            "overall_score": round(avg_overall, 2),
            "avg_relevance": round(avg_relevance, 2),
            "avg_clarity": round(avg_clarity, 2),
            "avg_depth": round(avg_depth, 2),
            "strengths": strengths,
            "improvements": improvements,
        }


# Singleton instance
evaluation_engine_service = EvaluationEngineService()
