"""
DB-backed interview session helpers.
Thin wrappers around services/crud.py that provide a familiar API for routes.
These replace the old in-memory dict-based store.
"""

import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_models import Interview, InterviewStatus, Question
from services import crud


async def create_session(
    db: AsyncSession,
    resume_data: dict,
    job_description: str,
    user_id: uuid.UUID | None = None,
) -> Interview:
    """Create a new interview session in DB."""
    interview = await crud.create_interview(
        db=db,
        job_description=job_description,
        resume_data=resume_data,
        user_id=user_id,
    )
    await crud.update_interview_status(db, interview, InterviewStatus.ACTIVE)
    return interview


async def get_session(db: AsyncSession, session_id: str) -> Interview | None:
    """Retrieve an interview session by ID."""
    try:
        interview_uuid = uuid.UUID(session_id)
    except ValueError:
        return None
    return await crud.get_interview(db, interview_uuid)


async def add_questions_to_session(
    db: AsyncSession,
    interview_id: uuid.UUID,
    questions_data: list[dict],
) -> list[Question]:
    """Bulk-insert questions for an interview and update total count."""
    questions = await crud.create_questions_bulk(db, interview_id, questions_data)
    interview = await crud.get_interview(db, interview_id)
    if interview:
        interview.total_questions = len(questions)
        await db.flush()
    return questions


async def complete_session(db: AsyncSession, interview: Interview) -> Interview:
    """Mark an interview as complete."""
    return await crud.update_interview_status(db, interview, InterviewStatus.COMPLETE)
