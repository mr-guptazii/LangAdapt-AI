"use client";

import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { ChatBubble } from "@/components/chat/ChatBubble";
import { CorrectionCard } from "@/components/chat/CorrectionCard";
import { AgentDecisionCard } from "@/components/chat/AgentDecisionCard";
import { SpeechFeedbackCard, type PronunciationInfo, type SpeechMetrics } from "@/components/voice/SpeechFeedbackCard";
import { Waveform } from "@/components/voice/Waveform";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Mic, Send, Loader2, Square, Volume2 } from "lucide-react";
import { api } from "@/lib/api";
import { motion } from "framer-motion";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";

interface Correction { type: string; category: string; incorrect: string; correct: string; severity: string; explanation: string; }
interface ChatMessage {
  id: string; role: "user" | "assistant"; content: string;
  corrections?: Correction[]; teachingStrategy?: string | null; difficultyDecision?: string | null;
  recommendedActivity?: { reason: string; target_skill_code: string } | null; agentsInvoked?: string[];
  speechMetrics?: SpeechMetrics; pronunciation?: PronunciationInfo | null; isMockVoice?: boolean; isMock?: boolean;
}
interface SendMessageResponse {
  session_id: string; response: string; follow_up_question: string; corrections: Correction[];
  teaching_strategy: string | null; difficulty_decision: string | null;
  recommended_activity: { reason: string; target_skill_code: string } | null; agents_invoked: string[];
  is_mock: boolean;
}
interface TranscribeResponse {
  session_id: string; transcript: string; is_mock: boolean;
  pronunciation: PronunciationInfo | null; speech_metrics: SpeechMetrics;
}
interface SynthesizeResponse {
  provider: string; is_mock: boolean; mime_type: string; audio_base64: string | null;
}

const MODES = ["conversation", "grammar", "vocabulary", "speaking", "free_talk"];

export default function TutorPage() {
  const [mode, setMode] = useState("conversation");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "welcome", role: "assistant", content: "Hi! I'm your AI tutor. What would you like to talk about today?" },
  ]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [voiceReplies, setVoiceReplies] = useState(true);
  const [ttsIsMock, setTtsIsMock] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const recorder = useVoiceRecorder();

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, thinking]);

  async function send(text: string, extra?: Partial<ChatMessage>) {
    if (!text.trim() || thinking) return;
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text, ...extra };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setThinking(true);
    try {
      const res = await api.post<SendMessageResponse>("/api/v1/chat/message", {
        session_id: sessionId, message: text, mode, input_mode: extra ? "voice" : "text",
      });
      setSessionId(res.session_id);
      const replyText = `${res.response} ${res.follow_up_question}`.trim();
      setMessages((m) => [...m, {
        id: crypto.randomUUID(), role: "assistant", content: replyText,
        corrections: res.corrections, teachingStrategy: res.teaching_strategy, difficultyDecision: res.difficulty_decision,
        recommendedActivity: res.recommended_activity, agentsInvoked: res.agents_invoked, isMock: res.is_mock,
      }]);
      if (voiceReplies) await speak(replyText);
    } catch {
      setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", content: "Sorry, something went wrong reaching the tutor." }]);
    } finally {
      setThinking(false);
    }
  }

  async function speak(text: string) {
    try {
      setSpeaking(true);
      const form = new FormData();
      form.append("text", text);
      form.append("voice_speed", "1.0");
      const res = await api.postForm<SynthesizeResponse>("/api/v1/voice/synthesize", form);
      setTtsIsMock(res.is_mock);
      if (res.audio_base64) {
        const audio = new Audio(`data:${res.mime_type};base64,${res.audio_base64}`);
        audioRef.current = audio;
        audio.onended = () => setSpeaking(false);
        await audio.play();
      } else if (typeof window !== "undefined" && "speechSynthesis" in window) {
        // Mock TTS provider returns no audio — fall back to the browser's own
        // speech synthesis so voice replies still work without an API key.
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.onend = () => setSpeaking(false);
        window.speechSynthesis.speak(utterance);
      } else {
        setSpeaking(false);
      }
    } catch {
      setSpeaking(false);
    }
  }

  async function startRecording() {
    window.speechSynthesis?.cancel();
    await recorder.start();
  }

  async function stopRecordingAndSend() {
    const blob = await recorder.stop();
    if (!blob || blob.size === 0) return;
    setThinking(true);
    try {
      const form = new FormData();
      if (sessionId) form.append("session_id", sessionId);
      form.append("audio", blob, "recording.webm");
      const res = await api.postForm<TranscribeResponse>("/api/v1/voice/transcribe", form);
      setSessionId(res.session_id);
      if (!res.transcript.trim()) {
        setThinking(false);
        return;
      }
      setThinking(false);
      await send(res.transcript, { speechMetrics: res.speech_metrics, pronunciation: res.pronunciation, isMockVoice: res.is_mock });
    } catch {
      setThinking(false);
      setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", content: "I couldn't process that recording — please try again." }]);
    }
  }

  async function onMicClick() {
    if (recorder.state === "recording") {
      await stopRecordingAndSend();
    } else if (recorder.state === "idle" || recorder.state === "error") {
      await startRecording();
    }
  }

  const micLabel = recorder.state === "recording" ? "Stop recording" : recorder.state === "requesting" ? "Requesting microphone…" : "Start recording";

  return (
    <AppShell>
      <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-4xl flex-col">
        <div className="flex items-center justify-between">
          <h1 className="font-display text-2xl text-gold-400">AI Tutor</h1>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs text-cream/50" title={ttsIsMock ? "No production voice provider is configured — using your device's built-in voice instead." : undefined}>
              <input type="checkbox" checked={voiceReplies} onChange={(e) => setVoiceReplies(e.target.checked)} className="accent-cyan-500" />
              Voice replies{voiceReplies && ttsIsMock ? " (device voice)" : ""}
            </label>
            <div className="flex gap-1.5 overflow-x-auto">
              {MODES.map((m) => (
                <button key={m} onClick={() => setMode(m)}
                  className={`whitespace-nowrap rounded-lg border px-3 py-1 text-xs capitalize ${mode === m ? "border-cyan-500 bg-cyan-500/10 text-cyan-300" : "border-white/10 text-cream/50"}`}>
                  {m.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div ref={scrollRef} className="mt-4 flex-1 space-y-4 overflow-y-auto rounded-2xl border border-white/5 p-4">
          {messages.map((m) => (
            <div key={m.id} className="space-y-2">
              <ChatBubble role={m.role}>{m.content}</ChatBubble>
              {m.isMock && (
                <p className="px-1 text-[11px] text-gold-400/70">
                  Demo reply — no real AI provider configured, so this response was generated by a rule-based mock, not a real model.
                </p>
              )}
              {m.speechMetrics && (
                <SpeechFeedbackCard metrics={m.speechMetrics} pronunciation={m.pronunciation ?? null} isMock={!!m.isMockVoice} />
              )}
              {m.corrections?.map((c, i) => <CorrectionCard key={i} correction={c} />)}
              {m.role === "assistant" && m.agentsInvoked && (
                <AgentDecisionCard
                  teachingStrategy={m.teachingStrategy}
                  difficultyDecision={m.difficultyDecision}
                  recommendedActivity={m.recommendedActivity}
                  agentsInvoked={m.agentsInvoked}
                />
              )}
            </div>
          ))}
          {thinking && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2 text-xs text-cream/40">
              <Loader2 size={14} className="animate-spin" /> AI is thinking…
            </motion.div>
          )}
          {speaking && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2 text-xs text-cream/40">
              <Volume2 size={14} className="animate-pulse-soft" /> Speaking…
            </motion.div>
          )}
        </div>

        {recorder.state === "recording" && (
          <div className="mt-2"><Waveform levels={recorder.levels} active /></div>
        )}
        {recorder.error && <p className="mt-1 text-center text-xs text-red-300">{recorder.error}</p>}

        <Card className="mt-2 flex items-center gap-2 p-3">
          <button
            onClick={onMicClick}
            aria-label={micLabel}
            disabled={recorder.state === "requesting" || recorder.state === "processing" || thinking}
            className={`focus-ring flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition-colors disabled:opacity-50 ${recorder.state === "recording" ? "bg-red-500/20 text-red-300 animate-pulse-soft" : "bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20"}`}
          >
            {recorder.state === "recording" ? <Square size={16} /> : recorder.state === "requesting" || recorder.state === "processing" ? <Loader2 size={18} className="animate-spin" /> : <Mic size={18} />}
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(input)}
            placeholder="Type your message, or press the mic to speak…"
            className="focus-ring flex-1 bg-transparent text-sm text-cream placeholder:text-cream/30"
          />
          <Button size="sm" onClick={() => send(input)} disabled={thinking || !input.trim()}>
            <Send size={16} />
          </Button>
        </Card>
      </div>
    </AppShell>
  );
}
