/**
 * useInterview — Custom hook for interview session state management.
 * Uses useReducer for predictable state transitions across the full interview lifecycle.
 *
 * States: idle → uploading → setup → interviewing → evaluating → complete
 */

import { useReducer, useCallback } from 'react';
import * as api from '../services/api';

// ── Initial State ──
const initialState = {
  status: 'idle', // idle | uploading | setup | interviewing | evaluating | complete
  error: null,

  // Resume
  resumeData: null,
  resumeFile: null,

  // Interview session
  sessionId: null,
  jobDescription: '',
  currentQuestion: null,
  questionIndex: 0,
  totalQuestions: 0,

  // Answers & scores
  answers: [],
  currentTranscript: '',
  isRecording: false,

  // Report
  report: null,
};

// ── Action Types ──
const ACTIONS = {
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR',

  UPLOAD_START: 'UPLOAD_START',
  UPLOAD_SUCCESS: 'UPLOAD_SUCCESS',

  SET_JOB_DESCRIPTION: 'SET_JOB_DESCRIPTION',

  INTERVIEW_START: 'INTERVIEW_START',
  INTERVIEW_STARTED: 'INTERVIEW_STARTED',

  SET_RECORDING: 'SET_RECORDING',
  SET_TRANSCRIPT: 'SET_TRANSCRIPT',

  SUBMIT_ANSWER_START: 'SUBMIT_ANSWER_START',
  SUBMIT_ANSWER_SUCCESS: 'SUBMIT_ANSWER_SUCCESS',

  INTERVIEW_COMPLETE: 'INTERVIEW_COMPLETE',
  REPORT_LOADED: 'REPORT_LOADED',

  RESET: 'RESET',
};

// ── Reducer ──
function interviewReducer(state, action) {
  switch (action.type) {
    case ACTIONS.SET_ERROR:
      return { ...state, error: action.payload, status: state.status === 'uploading' ? 'idle' : state.status };

    case ACTIONS.CLEAR_ERROR:
      return { ...state, error: null };

    case ACTIONS.UPLOAD_START:
      return { ...state, status: 'uploading', error: null, resumeFile: action.payload };

    case ACTIONS.UPLOAD_SUCCESS:
      return { ...state, status: 'setup', resumeData: action.payload };

    case ACTIONS.SET_JOB_DESCRIPTION:
      return { ...state, jobDescription: action.payload };

    case ACTIONS.INTERVIEW_START:
      return { ...state, status: 'interviewing', error: null };

    case ACTIONS.INTERVIEW_STARTED:
      return {
        ...state,
        status: 'interviewing',
        sessionId: action.payload.session_id,
        totalQuestions: action.payload.total_questions,
        currentQuestion: action.payload.first_question,
        questionIndex: 1,
      };

    case ACTIONS.SET_RECORDING:
      return { ...state, isRecording: action.payload };

    case ACTIONS.SET_TRANSCRIPT:
      return { ...state, currentTranscript: action.payload };

    case ACTIONS.SUBMIT_ANSWER_START:
      return { ...state, status: 'evaluating', error: null };

    case ACTIONS.SUBMIT_ANSWER_SUCCESS: {
      const { score, next_question, interview_complete } = action.payload;
      const newAnswer = {
        questionId: state.currentQuestion?.question_id,
        question: state.currentQuestion?.question_text,
        transcript: state.currentTranscript,
        score,
      };
      return {
        ...state,
        status: interview_complete ? 'complete' : 'interviewing',
        answers: [...state.answers, newAnswer],
        currentQuestion: next_question || null,
        questionIndex: interview_complete ? state.questionIndex : state.questionIndex + 1,
        currentTranscript: '',
        isRecording: false,
      };
    }

    case ACTIONS.REPORT_LOADED:
      return { ...state, report: action.payload };

    case ACTIONS.RESET:
      return { ...initialState };

    default:
      return state;
  }
}

// ── Hook ──
export function useInterview() {
  const [state, dispatch] = useReducer(interviewReducer, initialState);

  // Upload resume
  const uploadResume = useCallback(async (file) => {
    dispatch({ type: ACTIONS.UPLOAD_START, payload: file });
    try {
      const result = await api.uploadResume(file);
      if (result.success) {
        dispatch({ type: ACTIONS.UPLOAD_SUCCESS, payload: result.data });
      } else {
        dispatch({ type: ACTIONS.SET_ERROR, payload: result.message || 'Upload failed' });
      }
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: err.response?.data?.detail || 'Failed to upload resume' });
    }
  }, []);

  // Set job description
  const setJobDescription = useCallback((text) => {
    dispatch({ type: ACTIONS.SET_JOB_DESCRIPTION, payload: text });
  }, []);

  // Start interview session
  const startInterview = useCallback(async () => {
    dispatch({ type: ACTIONS.INTERVIEW_START });
    try {
      const result = await api.startInterview(state.resumeData, state.jobDescription);
      dispatch({ type: ACTIONS.INTERVIEW_STARTED, payload: result });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: err.response?.data?.detail || 'Failed to start interview' });
    }
  }, [state.resumeData, state.jobDescription]);

  // Set recording state
  const setRecording = useCallback((isRecording) => {
    dispatch({ type: ACTIONS.SET_RECORDING, payload: isRecording });
  }, []);

  // Set transcript
  const setTranscript = useCallback((text) => {
    dispatch({ type: ACTIONS.SET_TRANSCRIPT, payload: text });
  }, []);

  // Submit answer
  const submitAnswer = useCallback(async (transcript) => {
    if (!transcript && !state.currentTranscript) return;

    const finalTranscript = transcript || state.currentTranscript;
    dispatch({ type: ACTIONS.SET_TRANSCRIPT, payload: finalTranscript });
    dispatch({ type: ACTIONS.SUBMIT_ANSWER_START });

    try {
      const result = await api.submitAnswer(
        state.sessionId,
        state.currentQuestion.question_id,
        finalTranscript,
      );
      dispatch({ type: ACTIONS.SUBMIT_ANSWER_SUCCESS, payload: result });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: err.response?.data?.detail || 'Failed to submit answer' });
    }
  }, [state.sessionId, state.currentQuestion, state.currentTranscript]);

  // Load report
  const loadReport = useCallback(async (sessionId) => {
    try {
      const result = await api.getReport(sessionId || state.sessionId);
      dispatch({ type: ACTIONS.REPORT_LOADED, payload: result });
    } catch (err) {
      dispatch({ type: ACTIONS.SET_ERROR, payload: err.response?.data?.detail || 'Failed to load report' });
    }
  }, [state.sessionId]);

  // Reset
  const resetInterview = useCallback(() => {
    dispatch({ type: ACTIONS.RESET });
  }, []);

  // Clear error
  const clearError = useCallback(() => {
    dispatch({ type: ACTIONS.CLEAR_ERROR });
  }, []);

  return {
    state,
    uploadResume,
    setJobDescription,
    startInterview,
    setRecording,
    setTranscript,
    submitAnswer,
    loadReport,
    resetInterview,
    clearError,
  };
}
