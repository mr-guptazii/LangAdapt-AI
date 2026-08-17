"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { api, ApiError } from "@/lib/api";
import { CheckCircle2, XCircle } from "lucide-react";

interface Question {
  id: string; question_type: string; difficulty: string; prompt: string; options: string[] | null;
}
interface SubmitResult { is_correct: boolean; correct_answer: string; explanation: string; new_mastery: number | null; mastery_delta: number | null; }

const INSTRUCTIONS: Record<string, string> = {
  fill_blank: "Fill in the blank — type the complete sentence.",
  correction: "This sentence has a mistake — type the corrected sentence.",
  transformation: "Rewrite the sentence as instructed above.",
  multiple_choice: "Choose the correct option.",
  free_response: "Write your response below.",
};

export default function PracticePage() {
  const [skillCode, setSkillCode] = useState("");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<SubmitResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [started, setStarted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setLoading(true);
    setStarted(true);
    setError(null);
    try {
      const qs = await api.get<Question[]>(`/api/v1/practice/next${skillCode ? `?skill_code=${skillCode}` : ""}`);
      setQuestions(qs);
      setIndex(0);
      setResult(null);
      if (qs.length === 0) setError("Couldn't generate exercises right now — please try again.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't reach the server — please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function submit() {
    const q = questions[index];
    if (!q) return;
    const res = await api.post<SubmitResult>("/api/v1/practice/submit", { question_id: q.id, answer, response_time_ms: 4000 });
    setResult(res);
  }

  function next() {
    setAnswer("");
    setResult(null);
    setIndex((i) => i + 1);
  }

  const question = questions[index];

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl">
        <h1 className="font-display text-2xl text-gold-400">Adaptive practice</h1>
        <p className="mt-1 text-sm text-cream/60">Exercises are generated from your real mistakes and due reviews — never random.</p>

        {!started && (
          <Card className="mt-6">
            <CardTitle>What should we strengthen?</CardTitle>
            <p className="mt-2 text-sm text-cream/50">Leave blank to auto-pick your top weakness.</p>
            <input
              value={skillCode} onChange={(e) => setSkillCode(e.target.value)} placeholder="e.g. past_tense (optional)"
              className="focus-ring mt-3 w-full rounded-xl border border-white/10 bg-navy-800/60 px-4 py-2.5 text-sm text-cream"
            />
            <Button className="mt-4" onClick={start} disabled={loading}>{loading ? "Generating…" : "Start practice"}</Button>
          </Card>
        )}

        {started && loading && <p className="mt-8 text-cream/40">Generating personalized exercises…</p>}

        {started && !loading && error && (
          <Card className="mt-6">
            <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-200">
              <XCircle size={16} />
              {error}
            </div>
            <Button className="mt-4" onClick={start}>Try again</Button>
          </Card>
        )}

        {started && !loading && !error && question && (
          <Card className="mt-6">
            <div className="flex items-center justify-between">
              <Badge tone="gold">{question.difficulty}</Badge>
              <span className="text-xs text-cream/40">Question {index + 1} of {questions.length}</span>
            </div>
            <p className="mt-4 text-xs uppercase tracking-wide text-cream/40">
              {INSTRUCTIONS[question.question_type] ?? "Answer below."}
            </p>
            <p className="mt-1 text-cream">{question.prompt}</p>

            {question.options ? (
              <div className="mt-4 space-y-2">
                {question.options.map((opt) => (
                  <button key={opt} disabled={!!result} onClick={() => setAnswer(opt)}
                    className={`block w-full rounded-lg border px-4 py-2.5 text-left text-sm ${answer === opt ? "border-cyan-500 bg-cyan-500/10 text-cyan-200" : "border-white/10 text-cream/70"}`}>
                    {opt}
                  </button>
                ))}
              </div>
            ) : (
              <input
                value={answer} onChange={(e) => setAnswer(e.target.value)} disabled={!!result}
                className="focus-ring mt-4 w-full rounded-xl border border-white/10 bg-navy-800/60 px-4 py-2.5 text-sm text-cream"
              />
            )}

            {!result ? (
              <Button className="mt-5" disabled={!answer} onClick={submit}>Check answer</Button>
            ) : (
              <div className="mt-5 space-y-3">
                <div className={`flex items-center gap-2 rounded-xl border p-3 text-sm ${result.is_correct ? "border-cyan-500/30 bg-cyan-500/5 text-cyan-200" : "border-red-500/30 bg-red-500/5 text-red-200"}`}>
                  {result.is_correct ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                  {result.is_correct ? "Correct!" : `Not quite — correct answer: ${result.correct_answer}`}
                </div>
                <p className="text-sm text-cream/60">{result.explanation}</p>
                {result.new_mastery !== null && (
                  <p className="text-xs text-cream/40">
                    Mastery: {Math.round(result.new_mastery * 100)}% ({(result.mastery_delta ?? 0) >= 0 ? "+" : ""}{Math.round((result.mastery_delta ?? 0) * 100)}%)
                  </p>
                )}
                {index + 1 < questions.length ? (
                  <Button onClick={next}>Next question</Button>
                ) : (
                  <Button onClick={() => setStarted(false)} variant="secondary">Finish session</Button>
                )}
              </div>
            )}
          </Card>
        )}
      </div>
    </AppShell>
  );
}
