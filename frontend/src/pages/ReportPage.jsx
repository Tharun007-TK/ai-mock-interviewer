/**
 * ReportPage — Score breakdown, strengths/weaknesses, and PDF download.
 */

import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useInterviewContext } from '../context/InterviewContext';
import { getReportDownloadUrl } from '../services/api';
import ScoreCard from '../components/ScoreCard';

export default function ReportPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { state, loadReport, resetInterview } = useInterviewContext();

  useEffect(() => {
    if (sessionId) {
      loadReport(sessionId);
    }
  }, [sessionId, loadReport]);

  const report = state.report;

  function handleNewInterview() {
    resetInterview();
    navigate('/setup');
  }

  // Loading state
  if (!report) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-3 border-primary border-t-transparent" />
          <p className="text-sm text-text-muted">Loading report...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-12">
      <div className="mx-auto max-w-2xl space-y-8 animate-fade-in">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl font-bold text-text">Interview Report</h1>
          <p className="mt-2 text-sm text-text-muted">Session: {sessionId}</p>
        </div>

        {/* Overall Score */}
        <div className="rounded-2xl border border-text-muted/10 bg-surface-card p-8 text-center shadow-lg">
          <p className="mb-2 text-sm font-medium text-text-muted">Overall Score</p>
          <div className="text-6xl font-bold">
            <span className={`
              bg-clip-text text-transparent bg-gradient-to-r
              ${report.overall_score >= 7 ? 'from-success to-accent'
                : report.overall_score >= 4 ? 'from-warning to-primary'
                : 'from-danger to-warning'
              }
            `}>
              {report.overall_score.toFixed(1)}
            </span>
            <span className="text-2xl text-text-muted"> / 10</span>
          </div>
          <p className="mt-2 text-sm text-text-muted">
            {report.total_questions} questions answered
          </p>
        </div>

        {/* Category Scores */}
        {report.category_scores?.length > 0 && (
          <div className="rounded-2xl border border-text-muted/10 bg-surface-card p-6 shadow-lg">
            <h2 className="mb-4 text-lg font-semibold text-text">Category Breakdown</h2>
            <div className="space-y-4">
              {report.category_scores.map((cat) => (
                <ScoreCard
                  key={cat.category}
                  label={`${cat.category} (${cat.questions_count} Q)`}
                  score={cat.average_score}
                />
              ))}
            </div>
          </div>
        )}

        {/* Strengths & Improvements */}
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          {/* Strengths */}
          <div className="rounded-2xl border border-success/20 bg-success/5 p-6">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-success">
              <span>💪</span> Strengths
            </h3>
            {report.strengths?.length > 0 ? (
              <ul className="space-y-2">
                {report.strengths.map((s, i) => (
                  <li key={i} className="text-sm text-text-muted">• {s}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-text-muted italic">Keep practicing to build strengths!</p>
            )}
          </div>

          {/* Improvements */}
          <div className="rounded-2xl border border-warning/20 bg-warning/5 p-6">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-warning">
              <span>🎯</span> Areas to Improve
            </h3>
            {report.improvements?.length > 0 ? (
              <ul className="space-y-2">
                {report.improvements.map((s, i) => (
                  <li key={i} className="text-sm text-text-muted">• {s}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-text-muted italic">Great job across the board!</p>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
          {/* Download PDF */}
          <a
            href={getReportDownloadUrl(sessionId)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-white
                       shadow-lg shadow-primary/25 transition-all hover:bg-primary-dark hover:-translate-y-0.5"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            Download PDF Report
          </a>

          {/* Start New */}
          <button
            onClick={handleNewInterview}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-text-muted/20 px-6 py-3
                       text-sm font-medium text-text transition-all hover:bg-surface-light hover:-translate-y-0.5"
          >
            Start New Interview
          </button>
        </div>
      </div>
    </div>
  );
}
