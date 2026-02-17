"""
AI Mock Interviewer – FastAPI Application Entry Point

Run with: uvicorn main:app --reload --host 0.0.0.0 --port 8000
Docs at:  http://localhost:8000/docs
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routes import upload, interview, answer, report, ws_interview

settings = get_settings()


# ── Lifespan (startup / shutdown) ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events.

    TODO: Initialize heavy resources here:
      - Initialize ChromaDB client
      - Load embedding model
      - Connect to PostgreSQL
    """
    print(f"🚀 {settings.APP_NAME} starting up...")
    yield
    print(f"🛑 {settings.APP_NAME} shutting down...")


# ── App Instance ──
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-powered 1:1 voice mock interview platform. "
        "Upload your resume, practice with adaptive questions, "
        "and get a structured evaluation report."
    ),
    version="0.1.0-mvp",
    lifespan=lifespan,
)


# ── CORS Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Register Routers ──
app.include_router(upload.router, prefix="/api")
app.include_router(interview.router, prefix="/api")
app.include_router(answer.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(ws_interview.router)  # WebSocket — no /api prefix


# ── Health Check ──
@app.get("/", tags=["Health"])
async def health_check():
    """Root health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "0.1.0-mvp",
    }


@app.get("/api/health", tags=["Health"])
async def api_health():
    """API health check with service status."""
    return {
        "status": "healthy",
        "services": {
            "resume_parser": "placeholder",
            "embeddings": "placeholder",
            "question_engine": "placeholder",
            "evaluation": "placeholder",
            "report_generator": "placeholder",
            "voice_processing": "placeholder",
        },
    }
