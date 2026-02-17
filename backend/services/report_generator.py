"""
Report Generator Service
- Aggregate session scores into a structured report
- Generate downloadable PDF using ReportLab

TODO: Implement full ReportLab PDF generation with styled layout.
"""

import os
from datetime import datetime


class ReportGeneratorService:
    """Generates interview reports and PDF downloads."""

    REPORTS_DIR = "./reports"

    def __init__(self):
        os.makedirs(self.REPORTS_DIR, exist_ok=True)

    async def generate_report_data(
        self,
        session_id: str,
        resume_data: dict,
        job_description: str,
        questions: list[dict],
        answers: list[dict],
        aggregated_scores: dict,
    ) -> dict:
        """
        Build the full report data structure.

        TODO: Enhance with LLM-generated summary and recommendations.
        """
        return {
            "session_id": session_id,
            "generated_at": datetime.utcnow().isoformat(),
            "candidate_name": resume_data.get("name", "Unknown"),
            "job_description_snippet": job_description[:200],
            "total_questions": len(questions),
            "total_answered": len(answers),
            "overall_score": aggregated_scores.get("overall_score", 0.0),
            "category_breakdown": aggregated_scores,
            "strengths": aggregated_scores.get("strengths", []),
            "improvements": aggregated_scores.get("improvements", []),
            "questions_and_answers": [
                {
                    "question": q.get("question_text", ""),
                    "answer": a.get("transcript", ""),
                    "score": a.get("score", {}),
                }
                for q, a in zip(questions, answers)
            ],
        }

    async def generate_pdf(self, report_data: dict) -> str:
        """
        Generate a PDF report using ReportLab.

        TODO: Implement full PDF generation with:
              - Header with candidate name and date
              - Overall score summary
              - Per-question breakdown with scores
              - Strengths and areas for improvement
              - Professional styling and branding

              Example ReportLab usage:
              from reportlab.lib.pagesizes import letter
              from reportlab.pdfgen import canvas

              pdf_path = f"{self.REPORTS_DIR}/{report_data['session_id']}.pdf"
              c = canvas.Canvas(pdf_path, pagesize=letter)
              c.drawString(72, 750, f"Interview Report - {report_data['candidate_name']}")
              ...
              c.save()
              return pdf_path

        For now, returns a placeholder path.
        """
        session_id = report_data.get("session_id", "unknown")
        pdf_path = os.path.join(self.REPORTS_DIR, f"{session_id}.pdf")

        # Placeholder: create empty file
        with open(pdf_path, "w") as f:
            f.write(f"[Placeholder PDF Report for session {session_id}]")

        return pdf_path

    async def get_report_path(self, session_id: str) -> str | None:
        """Check if a PDF report exists for a session."""
        pdf_path = os.path.join(self.REPORTS_DIR, f"{session_id}.pdf")
        if os.path.exists(pdf_path):
            return pdf_path
        return None


# Singleton instance
report_generator_service = ReportGeneratorService()
