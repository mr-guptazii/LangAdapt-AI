"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";

const LANGUAGES = [
  { code: "en", name: "English" }, { code: "es", name: "Spanish" }, { code: "fr", name: "French" },
  { code: "de", name: "German" }, { code: "it", name: "Italian" }, { code: "pt", name: "Portuguese" },
  { code: "ja", name: "Japanese" }, { code: "zh", name: "Mandarin Chinese" }, { code: "hi", name: "Hindi" },
];
const GOALS = ["travel", "academic", "career", "interview", "daily_conversation", "business", "exams", "immigration", "general_fluency"];
const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const INTERESTS = ["technology", "gaming", "movies", "sports", "business", "science", "music", "travel", "food"];

type AssessmentQuestion = { id: string; skill_area: string; difficulty: string; prompt: string; options: string[] | null };

export default function OnboardingPage() {
  const router = useRouter();
  const { hydrate } = useAuthStore();
  const [step, setStep] = useState(0);
  const [native, setNative] = useState("hi");
  const [target, setTarget] = useState("en");
  const [goals, setGoals] = useState<string[]>([]);
  const [level, setLevel] = useState("A2");
  const [interests, setInterests] = useState<string[]>([]);
  const [personality, setPersonality] = useState("encouraging");
  const [correctionStyle, setCorrectionStyle] = useState("balanced");
  const [submitting, setSubmitting] = useState(false);

  const [assessmentSessionId, setAssessmentSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<AssessmentQuestion | null>(null);
  const [answer, setAnswer] = useState("");
  const [assessmentResult, setAssessmentResult] = useState<{ cefr_level: string; strengths: string[]; weaknesses: string[] } | null>(null);

  const steps = ["Welcome", "Languages", "Goals", "Placement", "Preferences", "Done"];

  function toggle(list: string[], setList: (v: string[]) => void, value: string) {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  }

  async function startAssessment() {
    const res = await api.post<{ assessment_session_id: string; question: AssessmentQuestion }>("/api/v1/assessment/start");
    setAssessmentSessionId(res.assessment_session_id);
    setQuestion(res.question);
    setStep(3);
  }

  async function submitAnswer() {
    if (!assessmentSessionId || !question) return;
    const res = await api.post<{ completed: boolean; next_question: AssessmentQuestion | null; result: { cefr_level: string; strengths: string[]; weaknesses: string[] } | null }>(
      `/api/v1/assessment/${assessmentSessionId}/answer`,
      { question_id: question.id, answer }
    );
    setAnswer("");
    if (res.completed && res.result) {
      setAssessmentResult(res.result);
      setLevel(res.result.cefr_level);
    } else if (res.next_question) {
      setQuestion(res.next_question);
    }
  }

  async function complete() {
    setSubmitting(true);
    try {
      await api.post("/api/v1/onboarding/complete", {
        native_language_code: native,
        target_language_code: target,
        goal_types: goals.length ? goals : ["general_fluency"],
        self_estimated_level: level,
        interests,
        ai_personality: personality,
        correction_style: correctionStyle,
      });
      await hydrate();
      router.push("/dashboard");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-navy-950 px-6 py-12">
      <div className="pointer-events-none absolute inset-0 bg-grid-fade" />
      <Card className="relative w-full max-w-xl">
        <div className="mb-6 flex gap-1.5">
          {steps.map((_, i) => (
            <div key={i} className={`h-1 flex-1 rounded-full ${i <= step ? "bg-cyan-500" : "bg-white/10"}`} />
          ))}
        </div>

        <motion.div key={step} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.25 }}>
          {step === 0 && (
            <div>
              <h1 className="font-display text-2xl text-gold-400">Welcome to LingoAdapt</h1>
              <p className="mt-3 text-cream/60">
                We&apos;ll ask a few quick questions, run a short adaptive placement check, and build your personal learning profile.
              </p>
              <Button className="mt-6" onClick={() => setStep(1)}>Get started</Button>
            </div>
          )}

          {step === 1 && (
            <div>
              <h2 className="font-display text-xl text-gold-400">Your languages</h2>
              <p className="mt-1 text-sm text-cream/60">Native language</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {LANGUAGES.map((l) => (
                  <button key={l.code} onClick={() => setNative(l.code)}
                    className={`rounded-lg border px-3 py-1.5 text-sm ${native === l.code ? "border-cyan-500 bg-cyan-500/10 text-cyan-300" : "border-white/10 text-cream/60"}`}>
                    {l.name}
                  </button>
                ))}
              </div>
              <p className="mt-4 text-sm text-cream/60">Learning</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {LANGUAGES.filter((l) => l.code !== native).map((l) => (
                  <button key={l.code} onClick={() => setTarget(l.code)}
                    className={`rounded-lg border px-3 py-1.5 text-sm ${target === l.code ? "border-gold-500 bg-gold-500/10 text-gold-300" : "border-white/10 text-cream/60"}`}>
                    {l.name}
                  </button>
                ))}
              </div>
              <Button className="mt-6" onClick={() => setStep(2)}>Continue</Button>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="font-display text-xl text-gold-400">What are your goals?</h2>
              <p className="mt-1 text-sm text-cream/60">Pick as many as apply.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {GOALS.map((g) => (
                  <button key={g} onClick={() => toggle(goals, setGoals, g)}
                    className={`rounded-lg border px-3 py-1.5 text-sm capitalize ${goals.includes(g) ? "border-cyan-500 bg-cyan-500/10 text-cyan-300" : "border-white/10 text-cream/60"}`}>
                    {g.replace("_", " ")}
                  </button>
                ))}
              </div>
              <div className="mt-6 flex gap-2">
                <Button variant="secondary" onClick={startAssessment}>Take placement assessment</Button>
                <Button variant="ghost" onClick={() => setStep(4)}>Skip — I&apos;ll self-estimate</Button>
              </div>
            </div>
          )}

          {step === 3 && !assessmentResult && question && (
            <div>
              <h2 className="font-display text-xl text-gold-400">Quick placement check</h2>
              <p className="mt-1 text-xs uppercase tracking-wide text-cream/40">{question.skill_area} · {question.difficulty}</p>
              <p className="mt-4 text-cream">{question.prompt}</p>
              {question.options ? (
                <div className="mt-4 space-y-2">
                  {question.options.map((opt) => (
                    <button key={opt} onClick={() => setAnswer(opt)}
                      className={`block w-full rounded-lg border px-4 py-2.5 text-left text-sm ${answer === opt ? "border-cyan-500 bg-cyan-500/10 text-cyan-200" : "border-white/10 text-cream/70"}`}>
                      {opt}
                    </button>
                  ))}
                </div>
              ) : (
                <textarea
                  value={answer} onChange={(e) => setAnswer(e.target.value)} rows={4}
                  className="focus-ring mt-4 w-full rounded-xl border border-white/10 bg-navy-800/60 p-3 text-sm text-cream"
                />
              )}
              <Button className="mt-6" disabled={!answer} onClick={submitAnswer}>Next question</Button>
            </div>
          )}

          {step === 3 && assessmentResult && (
            <div>
              <h2 className="font-display text-xl text-gold-400">Your estimated level: {assessmentResult.cefr_level}</h2>
              {assessmentResult.strengths.length > 0 && (
                <p className="mt-3 text-sm text-cream/70"><span className="text-cyan-400">Strengths:</span> {assessmentResult.strengths.join(", ")}</p>
              )}
              {assessmentResult.weaknesses.length > 0 && (
                <p className="mt-1 text-sm text-cream/70"><span className="text-gold-400">Focus areas:</span> {assessmentResult.weaknesses.join(", ")}</p>
              )}
              <Button className="mt-6" onClick={() => setStep(4)}>Continue</Button>
            </div>
          )}

          {step === 3 && !question && !assessmentResult && (
            <div>
              <p className="text-cream/60">Preparing your first question…</p>
            </div>
          )}

          {step === 4 && (
            <div>
              <h2 className="font-display text-xl text-gold-400">Learning preferences</h2>
              {!assessmentResult && (
                <>
                  <p className="mt-3 text-sm text-cream/60">Self-estimated level</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {LEVELS.map((l) => (
                      <button key={l} onClick={() => setLevel(l)}
                        className={`rounded-lg border px-3 py-1.5 text-sm ${level === l ? "border-cyan-500 bg-cyan-500/10 text-cyan-300" : "border-white/10 text-cream/60"}`}>
                        {l}
                      </button>
                    ))}
                  </div>
                </>
              )}
              <p className="mt-4 text-sm text-cream/60">Interests (used to personalize topics)</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {INTERESTS.map((i) => (
                  <button key={i} onClick={() => toggle(interests, setInterests, i)}
                    className={`rounded-lg border px-3 py-1.5 text-sm capitalize ${interests.includes(i) ? "border-gold-500 bg-gold-500/10 text-gold-300" : "border-white/10 text-cream/60"}`}>
                    {i}
                  </button>
                ))}
              </div>
              <p className="mt-4 text-sm text-cream/60">Tutor personality</p>
              <select value={personality} onChange={(e) => setPersonality(e.target.value)}
                className="focus-ring mt-2 w-full rounded-xl border border-white/10 bg-navy-800/60 px-3 py-2 text-sm text-cream">
                {["friendly", "professional", "strict_coach", "encouraging", "casual", "minimalist"].map((p) => (
                  <option key={p} value={p}>{p.replace("_", " ")}</option>
                ))}
              </select>
              <p className="mt-4 text-sm text-cream/60">Correction style</p>
              <select value={correctionStyle} onChange={(e) => setCorrectionStyle(e.target.value)}
                className="focus-ring mt-2 w-full rounded-xl border border-white/10 bg-navy-800/60 px-3 py-2 text-sm text-cream">
                {["gentle", "balanced", "strict", "explain_all", "minimal"].map((c) => (
                  <option key={c} value={c}>{c.replace("_", " ")}</option>
                ))}
              </select>
              <Button className="mt-6" onClick={complete} disabled={submitting}>
                {submitting ? "Setting up your profile…" : "Complete setup"}
              </Button>
            </div>
          )}
        </motion.div>
      </Card>
    </main>
  );
}
