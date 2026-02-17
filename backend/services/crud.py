"""
CRUD Service — Async database operations for all ORM models.
All functions take AsyncSession as first arg (compatible with Depends(get_db)).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_models import (
    User,
    Interview,
    InterviewStatus,
    Question,
    Answer,
    Report,
)


# ──────────────────────────────────────────────
# User
# ──────────────────────────────────────────────

async def get_or_create_user(db: AsyncSession, email: str | None = None, name: str | None = None) -> User:
    """Get existing user by email or create anonymous user."""
    if email:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            return user

    user = User(email=email, name=name)
    db.add(user)
    await db.flush()
    return user


# ──────────────────────────────────────────────
# Interview
# ──────────────────────────────────────────────

async def create_interview(
    db: AsyncSession,
    job_description: str,
    resume_data: dict,
    user_id: uuid.UUID | None = None,
) -> Interview:
    """Create a new interview session in DB."""
    interview = Interview(
        user_id=user_id,
        job_description=job_description,
        resume_data=resume_data,
        status=InterviewStatus.PENDING,
    )
    db.add(interview)
    await db.flush()
    return interview


async def get_interview(db: AsyncSession, interview_id: uuid.UUID) -> Interview | None:
    """Fetch interview by ID with all relationships loaded."""
    result = await db.execute(
        select(Interview).where(Interview.id == interview_id)
    )
    return result.scalar_one_or_none()


async def update_interview_status(
    db: AsyncSession,
    interview: Interview,
    status: InterviewStatus,
) -> Interview:
    """Update the status of an interview."""
    interview.status = status
    if status == InterviewStatus.COMPLETE:
        interview.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return interview


async def increment_question_index(db: AsyncSession, interview: Interview) -> Interview:
    """Move to the next question."""
    interview.current_question_index += 1
    await db.flush()
    return interview


# ──────────────────────────────────────────────
# Question
# ──────────────────────────────────────────────

async def create_questions_bulk(
    db: AsyncSession,
    interview_id: uuid.UUID,
    questions_data: list[dict],
) -> list[Question]:
    """
    Bulk-create questions for an interview.
    Expects list of dicts: [{question_text, category, is_follow_up?}]
    """
    questions = []
    for idx, q in enumerate(questions_data):
        question = Question(
            interview_id=interview_id,
            order_index=idx,
            question_text=q["question_text"],
            category=q.get("category", "general"),
            is_follow_up=q.get("is_follow_up", False),
        )
        db.add(question)
        questions.append(question)
    await db.flush()
    return questions


async def get_questions_for_interview(
    db: AsyncSession,
    interview_id: uuid.UUID,
) -> list[Question]:
    """Get all questions for an interview, ordered by index."""
    result = await db.execute(
        select(Question)
        .where(Question.interview_id == interview_id)
        .order_by(Question.order_index)
    )
    return list(result.scalars().all())


async def get_question_by_index(
    db: AsyncSession,
    interview_id: uuid.UUID,
    order_index: int,
) -> Question | None:
    """Get a specific question by order index."""
    result = await db.execute(
        select(Question)
        .where(Question.interview_id == interview_id)
        .where(Question.order_index == order_index)
    )
    return result.scalar_one_or_none()


async def get_question_by_id(db: AsyncSession, question_id: uuid.UUID) -> Question | None:
    """Get a question by its UUID."""
    result = await db.execute(select(Question).where(Question.id == question_id))
    return result.scalar_one_or_none()


# ──────────────────────────────────────────────
# Answer
# ──────────────────────────────────────────────

async def create_answer(
    db: AsyncSession,
    interview_id: uuid.UUID,
    question_id: uuid.UUID,
    transcript: str,
    scores: dict,
    feedback: str = "",
) -> Answer:
    """Create an answer record with scores."""
    answer = Answer(
        interview_id=interview_id,
        question_id=question_id,
        transcript=transcript,
        scores=scores,
        feedback=feedback,
    )
    db.add(answer)
    await db.flush()
    return answer


async def get_answers_for_interview(
    db: AsyncSession,
    interview_id: uuid.UUID,
) -> list[Answer]:
    """Get all answers for an interview."""
    result = await db.execute(
        select(Answer).where(Answer.interview_id == interview_id)
    )
    return list(result.scalars().all())


# ──────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────

async def create_report(
    db: AsyncSession,
    interview_id: uuid.UUID,
    overall_score: float,
    category_scores: list[dict],
    strengths: list[str],
    improvements: list[str],
    pdf_path: str | None = None,
) -> Report:
    """Create or update a report for an interview."""
    # Check if report already exists
    result = await db.execute(
        select(Report).where(Report.interview_id == interview_id)
    )
    report = result.scalar_one_or_none()

    if report:
        report.overall_score = overall_score
        report.category_scores = category_scores
        report.strengths = strengths
        report.improvements = improvements
        report.pdf_path = pdf_path
    else:
        report = Report(
            interview_id=interview_id,
            overall_score=overall_score,
            category_scores=category_scores,
            strengths=strengths,
            improvements=improvements,
            pdf_path=pdf_path,
        )
        db.add(report)

    await db.flush()
    return report


async def get_report(db: AsyncSession, interview_id: uuid.UUID) -> Report | None:
    """Get report for a given interview."""
    result = await db.execute(
        select(Report).where(Report.interview_id == interview_id)
    )
    return result.scalar_one_or_none()
