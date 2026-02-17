/**
 * InterviewPage — Live interview session with real-time WebSocket communication.
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useInterviewContext } from '../context/InterviewContext';
import { useWebSocketInterview } from '../hooks/useWebSocketInterview';
import InterviewPanel from '../components/InterviewPanel';

export default function InterviewPage() {
  const navigate = useNavigate();
  // Get session ID from global context (set during Setup)
  const { state: globalState } = useInterviewContext();
  const sessionId = globalState.sessionId;

  // Use WebSocket hook for real-time interaction
  const {
    status,               // connection status
    interviewState,       // server logic state (waiting_for_answer, ai_speaking, etc.)
    currentQuestion,
    transcript,
    scores,
    error,
    isAiSpeaking,         // audio player state
    sendAudioChunk,
    sendEndUtterance,
  } = useWebSocketInterview(sessionId);

  // Redirect if no session logic...
  // However, useWebSocketInterview handles connection.
  // If we don't have a sessionId from context, we should redirect.
  useEffect(() => {
    if (!sessionId) {
      console.warn('No session ID found, redirecting to setup');
      navigate('/setup');
    }
  }, [sessionId, navigate]);

  // Navigate to report when complete
  useEffect(() => {
    // If WS says complete or connection closed cleanly after finish
    if (status === 'complete') {
      navigate(`/report/${sessionId}`);
    }
  }, [status, sessionId, navigate]);

  // Handle recording controls
  function handleRecordingChange(isRecording) {
    if (!isRecording) {
      // User stopped recording manually -> signal end of turn
      sendEndUtterance();
      // Clear transcript preview? No, keep it until next question.
    }
  }

  return (
    <div className="min-h-screen px-4 py-8 bg-background">
      {/* Header */}
      <header className="mx-auto mb-8 max-w-2xl text-center">
        <h1 className="text-2xl font-bold text-text">Interview Session</h1>
        <p className="mt-1 text-sm text-text-muted">
          {status === 'connecting' ? 'Connecting to server...' : 
           status === 'error' ? 'Connection Error' :
           'Listen to the question, then answer naturally.'}
        </p>
      </header>

      {/* Error */}
      {error && (
        <div className="mx-auto mb-6 max-w-2xl rounded-lg bg-red-500/10 border border-red-500/20 p-4 text-sm text-red-500">
          {error}
        </div>
      )}

      {/* Connection Status */}
      {status === 'connecting' && (
         <div className="mx-auto max-w-2xl text-center py-20">
            <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mx-auto mb-4"></div>
            <p className="text-text-muted">Establishing secure connection...</p>
         </div>
      )}

      {/* Interview Panel */}
      {status === 'connected' && (
        <InterviewPanel
          question={currentQuestion}
          questionIndex={currentQuestion?.question_id || 1} // Fallback
          totalQuestions={globalState.totalQuestions || 5}  // Fallback
          
          isEvaluating={interviewState === 'analyzing_partial' || interviewState === 'ai_speaking'} 
          // Note: "evaluating" in old logic meant waiting for result. 
          // Here we use state. But we can simplify:
          // Just pass isAiSpeaking to disable specific interactions if needed.
          // But actually, we want to allow barge-in? 
          // For now, let's keep it simple: disable mic only during 'evaluating' or 'ai_speaking' if we want strictly turn-based.
          // The VoiceRecorder has `forceStop={isAiSpeaking}` which handles the automated stop.
          
          isAiSpeaking={isAiSpeaking}
          onAudioData={sendAudioChunk}
          onRecordingChange={handleRecordingChange}
        />
      )}

      {/* Transcript Preview (Live) */}
      {transcript && (
        <div className="mx-auto mt-8 max-w-2xl rounded-lg bg-surface-light/50 p-4 text-sm text-text-muted transition-all">
          <p className="text-xs font-semibold text-text mb-1 uppercase tracking-wide">Live Transcript</p>
          <p className="italic leading-relaxed">{transcript}</p>
        </div>
      )}
      
      {/* Scores Preview (Debug or Feedback) */}
      {/* 
      {scores && (
         <div className="mx-auto mt-4 max-w-2xl p-4 border border-green-500/20 bg-green-500/5 rounded text-xs text-green-400">
            Received Score: {JSON.stringify(scores)}
         </div>
      )} 
      */}

    </div>
  );
}
