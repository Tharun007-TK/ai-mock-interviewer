/**
 * API Service — Axios client for all backend endpoints.
 * Base URL proxied through Vite dev server → FastAPI at :8000
 */

import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

/**
 * Upload a resume PDF file.
 * @param {File} file - PDF file object
 * @returns {Promise<{success, message, data}>}
 */
export async function uploadResume(file) {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post('/upload-resume', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

/**
 * Start a new interview session.
 * @param {object} resumeData - Parsed resume data from upload
 * @param {string} jobDescription - Job description text
 * @returns {Promise<{session_id, total_questions, first_question}>}
 */
export async function startInterview(resumeData, jobDescription) {
  const { data } = await api.post('/start-interview', {
    resume_data: resumeData,
    job_description: jobDescription,
  });
  return data;
}

/**
 * Submit an answer for evaluation.
 * @param {string} sessionId
 * @param {number} questionId
 * @param {string} transcript - User's answer text
 * @returns {Promise<{session_id, question_id, score, next_question, interview_complete}>}
 */
export async function submitAnswer(sessionId, questionId, transcript) {
  const { data } = await api.post('/answer', {
    session_id: sessionId,
    question_id: questionId,
    transcript,
  });
  return data;
}

/**
 * Get the evaluation report for a completed session.
 * @param {string} sessionId
 * @returns {Promise<{session_id, overall_score, category_scores, strengths, improvements, download_url}>}
 */
export async function getReport(sessionId) {
  const { data } = await api.get(`/report/${sessionId}`);
  return data;
}

/**
 * Get PDF download URL for a session.
 * @param {string} sessionId
 * @returns {string}
 */
export function getReportDownloadUrl(sessionId) {
  return `/api/report/${sessionId}/download`;
}

export default api;
