"use client";

import { useCallback, useRef, useState } from "react";

export type RecorderState = "idle" | "requesting" | "recording" | "processing" | "error";

interface UseVoiceRecorder {
  state: RecorderState;
  error: string | null;
  levels: number[]; // recent volume samples, 0..1, for waveform rendering
  start: () => Promise<void>;
  stop: () => Promise<Blob | null>;
}

/** Wraps the browser MediaRecorder + Web Audio API: real microphone capture
 * (not simulated) plus a rolling volume-level buffer for waveform rendering.
 * Falls back to a clear error state on unsupported browsers/denied permission
 * rather than silently pretending to record. */
export function useVoiceRecorder(): UseVoiceRecorder {
  const [state, setState] = useState<RecorderState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [levels, setLevels] = useState<number[]>([]);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const resolveStopRef = useRef<((blob: Blob | null) => void) | null>(null);

  const tickLevels = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const v = ((data[i] ?? 128) - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / data.length);
    setLevels((prev) => [...prev.slice(-39), Math.min(1, rms * 4)]);
    rafRef.current = requestAnimationFrame(tickLevels);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    setState("requesting");
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("Microphone access isn't supported in this browser.");
      setState("error");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      audioCtxRef.current = audioCtx;
      analyserRef.current = analyser;
      setLevels([]);
      rafRef.current = requestAnimationFrame(tickLevels);

      const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        resolveStopRef.current?.(blob);
        resolveStopRef.current = null;
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setState("recording");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not access the microphone.");
      setState("error");
    }
  }, [tickLevels]);

  const stop = useCallback((): Promise<Blob | null> => {
    setState("processing");
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    audioCtxRef.current?.close().catch(() => {});
    streamRef.current?.getTracks().forEach((t) => t.stop());

    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") {
      setState("idle");
      return Promise.resolve(null);
    }
    return new Promise((resolve) => {
      resolveStopRef.current = (blob) => {
        setState("idle");
        resolve(blob);
      };
      recorder.stop();
    });
  }, []);

  return { state, error, levels, start, stop };
}
