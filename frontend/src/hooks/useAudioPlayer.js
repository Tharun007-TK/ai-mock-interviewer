import { useState, useRef, useCallback, useEffect } from 'react';

/**
 * useAudioPlayer — Manages real-time audio playback from linear16 PCM chunks.
 *
 * Concepts:
 * - Maintains a `nextStartTime` pointer to schedule chunks gaplessly.
 * - Detects if we fell behind real-time (drift) and resets scheduling.
 * - Exposed `isPlaying` state based on scheduling.
 */
export function useAudioPlayer() {
  const [isPlaying, setIsPlaying] = useState(false);
  const audioContextRef = useRef(null);
  const nextStartTimeRef = useRef(0);
  const isScheduledRef = useRef(false);
  
  // Initialize context on user gesture (usually mount or first click)
  const initAudioContext = useCallback(() => {
    if (!audioContextRef.current) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      // standard 16kHz for Deepgram TTS
      audioContextRef.current = new AudioContext(); 
    }
    if (audioContextRef.current.state === 'suspended') {
      audioContextRef.current.resume();
    }
  }, []);

  /**
   * Convert base64 linear16 PCM (16kHz mono) to AudioBuffer.
   */
  const createAudioBuffer = (base64Data) => {
    const ctx = audioContextRef.current;
    if (!ctx) return null;

    const binaryString = window.atob(base64Data);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    const int16Array = new Int16Array(bytes.buffer);
    const float32Array = new Float32Array(int16Array.length);
    
    // Normalize Int16 to Float32 [-1.0, 1.0]
    for (let i = 0; i < int16Array.length; i++) {
      float32Array[i] = int16Array[i] / 32768.0;
    }

    const buffer = ctx.createBuffer(1, float32Array.length, 16000); // Source rate is 16k
    buffer.getChannelData(0).set(float32Array);
    return buffer;
  };

  /**
   * Enqueue a chunk for playback.
   */
  const addAudioChunk = useCallback((base64Data) => {
    initAudioContext();
    const ctx = audioContextRef.current;
    if (!ctx) return;

    const buffer = createAudioBuffer(base64Data);
    if (!buffer) return;

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);

    const currentTime = ctx.currentTime;
    
    // If next start time is in the past, reset to now (plus tiny safety margin)
    if (nextStartTimeRef.current < currentTime) {
      nextStartTimeRef.current = currentTime + 0.05;
    }

    source.start(nextStartTimeRef.current);
    nextStartTimeRef.current += buffer.duration;

    setIsPlaying(true);
    
    // When this chunk ends, check if we are truly done
    source.onended = () => {
        if (ctx.currentTime >= nextStartTimeRef.current - 0.1) {
            setIsPlaying(false);
        }
    };

  }, [initAudioContext]);

  /**
   * Stop all playback and reset.
   */
  const stop = useCallback(() => {
    if (audioContextRef.current) {
      audioContextRef.current.suspend(); 
      // Ideally we close/recreate or just suspend. 
      // Recreating is safer to clear scheduled nodes.
      audioContextRef.current.close().then(() => {
          audioContextRef.current = null;
          nextStartTimeRef.current = 0;
          setIsPlaying(false);
      });
    } else {
        setIsPlaying(false);
        nextStartTimeRef.current = 0;
    }
  }, []);

  return {
    isPlaying,
    addAudioChunk,
    initAudioContext,
    stop,
  };
}
