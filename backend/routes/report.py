"""
Route: GET /report/{session_id}
Generates and returns the interview evaluation report.
"""

import uuid

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.schemas import ReportResponse, CategoryScore, AnswerScore
from models.session import get_session
from models.db_models import InterviewStatus
from services import crud
from services.evaluation import evaluation_engine_service
from services.report_generator import report_generator_service

router = APIRouter(tags=["Report"])


@router.get("/report/{session_id}", response_model=ReportResponse)
async def get_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the interview evaluation report for a completed session.

    - Returns: Overall score, category scores, strengths, improvements, PDF download URL
    """
    interview = await get_session(db, session_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    if interview.status != InterviewStatus.COMPLETE:
        raise HTTPException(status_code=400, detail="Interview is still in progress.")

    # Load data from DB
    questions = await crud.get_questions_for_interview(db, interview.id)
    answers = await crud.get_answers_for_interview(db, interview.id)

    # Build AnswerScore objects from stored JSONB
    scores = [AnswerScore(**a.scores) for a in answers]

    # Aggregate scores
    aggregated = await evaluation_engine_service.aggregate_scores(scores)

    # Build category breakdown
    # Map question_id -> question for category lookup
    q_map = {q.id: q for q in questions}
    category_map: dict[str, list[float]] = {}
    for a in answers:
        q = q_map.get(a.question_id)
        cat = q.category if q else "general"
        if cat not in category_map:
            category_map[cat] = []
        category_map[cat].append(a.scores.get("overall", 0.0))

    category_scores = [
        CategoryScore(
            category=cat,
            average_score=round(sum(vals) / len(vals), 2),
            questions_count=len(vals),
        )
        for cat, vals in category_map.items()
    ]

    # Persist report in DB
    db_report = await crud.create_report(
        db=db,
        interview_id=interview.id,
        overall_score=aggregated["overall_score"],
        category_scores=[cs.model_dump() for cs in category_scores],
        strengths=aggregated.get("strengths", []),
        improvements=aggregated.get("improvements", []),
    )

    # Generate PDF
    questions_dicts = [
        {"question_text": q.question_text, "category": q.category} for q in questions
    ]
    answers_dicts = [
        {"transcript": a.transcript, "score": a.scores} for a in answers
    ]

    report_data = await report_generator_service.generate_report_data(
        session_id=session_id,
        resume_data=interview.resume_data,
        job_description=interview.job_description,
        questions=questions_dicts,
        answers=answers_dicts,
        aggregated_scores=aggregated,
    )

    pdf_path = await report_generator_service.generate_pdf(report_data)

    # Update report with PDF path
    db_report.pdf_path = pdf_path
    await db.flush()

    return ReportResponse(
        session_id=session_id,
        overall_score=aggregated["overall_score"],
        total_questions=len(questions),
        category_scores=category_scores,
        strengths=aggregated.get("strengths", []),
        improvements=aggregated.get("improvements", []),
        download_url=f"/report/{session_id}/download",
    )


@router.get("/report/{session_id}/download")
async def download_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download the PDF report for a completed session."""
    interview = await get_session(db, session_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Session not found.")

    report = await crud.get_report(db, interview.id)
    if not report or not report.pdf_path:
        raise HTTPException(status_code=404, detail="Report PDF not found.")

    return FileResponse(
        path=report.pdf_path,
        media_type="application/pdf",
        filename=f"interview_report_{session_id}.pdf",
    )
