"""
Route: POST /upload-resume
Accepts a PDF file upload, parses it, and returns structured resume data.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from models.schemas import ResumeUploadResponse
from services.resume_parser import resume_parser_service

router = APIRouter(tags=["Resume"])


@router.post("/upload-resume", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...)):
    """
    Upload a resume PDF for parsing.

    - Accepts: PDF file (multipart/form-data)
    - Returns: Structured resume data (name, email, skills, experience, education)
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted.",
        )

    # Read file bytes
    try:
        file_bytes = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read uploaded file.")

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Parse and structure resume
    try:
        parsed = await resume_parser_service.parse_and_structure(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return ResumeUploadResponse(
        success=True,
        message="Resume parsed successfully.",
        data=parsed,
    )
