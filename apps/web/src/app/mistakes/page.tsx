"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { api } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";

interface Mistake {
  id: string; category: string; error_type: string; description: string; occurrence_count: number;
  mastery: number; severity: string; trend: string; last_seen_at: string;
  examples: { incorrect: string; correct: string; explanation: string }[];
}

export default function MistakesPage() {
  const [mistakes, setMistakes] = useState<Mistake[]>([]);

  useEffect(() => {
    api.get<Mistake[]>("/api/v1/mistakes").then(setMistakes).catch(() => {});
  }, []);

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <h1 className="font-display text-2xl text-gold-400">Your Learning Memory</h1>
        <p className="mt-1 text-sm text-cream/60">Every recurring mistake the tutor has noticed, and how it&apos;s trending.</p>

        <div className="mt-6 space-y-4">
          {mistakes.length === 0 && <p className="text-sm text-cream/40">No mistakes recorded yet — they&apos;ll show up here as you practice.</p>}
          {mistakes.map((m) => (
            <Card key={m.id}>
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-display text-lg capitalize text-cream">{m.category.replace("_", " ")}</h2>
                  <p className="mt-1 text-sm text-cream/60">{m.description}</p>
                </div>
                <Badge tone={m.trend === "improving" ? "cyan" : m.trend === "worsening" ? "red" : "neutral"}>{m.trend}</Badge>
              </div>

              <div className="mt-3 flex items-center gap-4 text-xs text-cream/50">
                <span>{m.occurrence_count} mistakes</span>
                <span>Last seen {formatRelativeTime(m.last_seen_at)}</span>
                <Badge tone={m.severity === "high" ? "red" : "gold"}>{m.severity}</Badge>
              </div>

              <div className="mt-3">
                <div className="flex justify-between text-xs text-cream/40">
                  <span>Mastery</span>
                  <span>{Math.round(m.mastery * 100)}%</span>
                </div>
                <ProgressBar value={m.mastery} className="mt-1" />
              </div>

              {m.examples.length > 0 && (
                <div className="mt-4 space-y-2 border-t border-white/5 pt-3">
                  {m.examples.map((e, i) => (
                    <div key={i} className="text-sm">
                      <span className="text-cream/40 line-through">{e.incorrect}</span>
                      <span className="mx-2 text-cream/30">→</span>
                      <span className="text-cyan-300">{e.correct}</span>
                      <p className="mt-0.5 text-xs text-cream/50">{e.explanation}</p>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
