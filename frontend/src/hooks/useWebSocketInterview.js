import { useState, useEffect, useRef, useCallback } from 'react';
import { useAudioPlayer } from './useAudioPlayer';

const WS_URL = 'ws://localhost:8000/ws/interview'; // TODO: use env var

export function useWebSocketInterview(sessionId) {
  const [status, setStatus] = useState('connecting'); // connecting, connected, disconnected, error
  const [interviewState, setInterviewState] = useState('waiting_for_answer'); // server state
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [transcript, setTranscript] = useState(''); // Live partial transcript
  const [scores, setScores] = useState(null);
  const [error, setError] = useState(null);
  
  const wsRef = useRef(null);
  const { isPlaying: isAiSpeaking, addAudioChunk, initAudioContext, stop: stopAudio } = useAudioPlayer();

  // Connect to WebSocket
  useEffect(() => {
    if (!sessionId) return;

    setStatus('connecting');
    const ws = new WebSocket(`${WS_URL}/${sessionId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WS Connected');
      setStatus('connected');
      initAudioContext(); // Prepare audio context on successful connection (or user interaction)
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
      } catch (err) {
        console.error('WS parse error:', err);
      }
    };

    ws.onclose = () => {
      console.log('WS Disconnected');
      setStatus('disconnected');
    };

    ws.onerror = (err) => {
      console.error('WS Error:', err);
      setError('Connection error');
      setStatus('error');
    };

    return () => {
      ws.close();
      stopAudio();
    };
  }, [sessionId, initAudioContext, stopAudio]);

  // Message Handler
  const handleMessage = useCallback((msg) => {
    switch (msg.type) {
      case 'state_change':
        setInterviewState(msg.state);
        if (msg.state === 'ai_speaking' || msg.state === 'interrupting') {
           // AI is about to speak - mic should pause (handled by component via state)
        }
        break;

      case 'next_question':
        setCurrentQuestion(msg.question);
        setTranscript('');
        setScores(null);
        break;

      case 'transcript_partial':
        setTranscript(msg.text);
        break;

      case 'transcript_final':
        setTranscript(msg.text); // Finalize display
        break;
      
      case 'eval_score':
        setScores(msg.score);
        break;

      case 'tts_audio':
        // Received audio chunk -> queue for playback
        if (msg.data) {
          addAudioChunk(msg.data);
        }
        break;
      
      case 'interrupt':
        // Server says "Stop talking!"
        console.log('Interrupted by AI:', msg.reason);
        // We rely on state_change to 'interrupting' to update UI
        break;

      case 'interview_complete':
        setStatus('complete');
        break;

      case 'error':
        setError(msg.message);
        break;

      default:
        console.warn('Unknown WS message:', msg);
    }
  }, [addAudioChunk]);

  // ── Actions ──

  const sendAudioChunk = useCallback((base64Data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'audio_chunk',
        data: base64Data
      }));
    }
  }, []);

  const sendEndUtterance = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'end_utterance' }));
    }
  }, []);

  return {
    status,
    interviewState,
    currentQuestion,
    transcript,
    scores,
    error,
    isAiSpeaking, // derived from useAudioPlayer (or server state?)
    // Note: server state 'ai_speaking' is logically when AI *intends* to speak. 
    // isAiSpeaking from player is when audio is *actually* playing.
    // For mic control, use server state 'ai_speaking' | 'interrupting'.
    // For visualizer, use player state.
    
    sendAudioChunk,
    sendEndUtterance,
  };
}
