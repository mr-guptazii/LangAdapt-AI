"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardTitle } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { formatMinutes, formatRelativeTime } from "@/lib/utils";
import { Flame, Clock, ArrowRight } from "lucide-react";

interface DashboardData {
  cefr_level: string;
  streak_days: number;
  total_study_minutes: number;
  weekly_study_minutes: number;
  abilities: Record<string, number>;
  weak_areas: { skill_code: string; skill_name: string; mastery: number }[];
  vocabulary_counts: Record<string, number>;
  recent_mistakes: { category: string; occurrence_count: number; last_seen_at: string; trend: string }[];
}

interface Recommendation {
  id: string; activity_type: string; title: string; reason_summary: string; estimated_minutes: number;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [recs, setRecs] = useState<Recommendation[]>([]);

  useEffect(() => {
    api.get<DashboardData>("/api/v1/progress/dashboard").then(setData).catch(() => {});
    api.get<Recommendation[]>("/api/v1/recommendations").then(setRecs).catch(() => {});
  }, []);

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <h1 className="font-display text-2xl text-gold-400">Your dashboard</h1>
        <p className="mt-1 text-sm text-cream/60">Here&apos;s where your learning stands right now.</p>

        {!data ? (
          <p className="mt-8 text-cream/40">Loading your profile…</p>
        ) : (
          <>
            <div className="mt-6 grid gap-4 sm:grid-cols-4">
              <Card>
                <p className="text-xs uppercase tracking-wide text-cream/40">Level</p>
                <p className="mt-1 font-display text-3xl text-gold-400">{data.cefr_level}</p>
              </Card>
              <Card className="flex items-center gap-3">
                <Flame className="text-gold-400" />
                <div>
                  <p className="text-xs uppercase tracking-wide text-cream/40">Streak</p>
                  <p className="font-display text-2xl text-cream">{data.streak_days} days</p>
                </div>
              </Card>
              <Card className="flex items-center gap-3">
                <Clock className="text-cyan-400" />
                <div>
                  <p className="text-xs uppercase tracking-wide text-cream/40">This week</p>
                  <p className="font-display text-2xl text-cream">{formatMinutes(data.weekly_study_minutes)}</p>
                </div>
              </Card>
              <Card>
                <p className="text-xs uppercase tracking-wide text-cream/40">Total study time</p>
                <p className="mt-1 font-display text-2xl text-cream">{formatMinutes(data.total_study_minutes)}</p>
              </Card>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-3">
              <Card className="lg:col-span-2">
                <CardTitle>Recommended for you</CardTitle>
                <div className="mt-4 space-y-3">
                  {recs.length === 0 && <p className="text-sm text-cream/40">Generating your recommendations…</p>}
                  {recs.map((r) => (
                    <div key={r.id} className="flex items-center justify-between rounded-xl border border-white/5 p-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <Badge tone="cyan">{r.activity_type}</Badge>
                          <span className="text-sm font-medium text-cream">{r.title}</span>
                        </div>
                        <p className="mt-1 text-xs text-cream/50">{r.reason_summary}</p>
                      </div>
                      <Link href="/tutor">
                        <Button size="sm" variant="secondary">{r.estimated_minutes} min <ArrowRight size={14} /></Button>
                      </Link>
                    </div>
                  ))}
                </div>
              </Card>

              <Card>
                <CardTitle>Ability breakdown</CardTitle>
                <div className="mt-4 grid grid-cols-2 gap-4">
                  {Object.entries(data.abilities).slice(0, 4).map(([key, value]) => (
                    <div key={key} className="flex flex-col items-center gap-1">
                      <ProgressRing value={value} size={64} />
                      <span className="text-xs capitalize text-cream/50">{key}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <Card>
                <CardTitle>Weak areas</CardTitle>
                <div className="mt-4 space-y-3">
                  {data.weak_areas.length === 0 && <p className="text-sm text-cream/40">No weaknesses tracked yet — keep practicing!</p>}
                  {data.weak_areas.map((w) => (
                    <div key={w.skill_code}>
                      <div className="flex justify-between text-sm">
                        <span className="text-cream/80">{w.skill_name}</span>
                        <span className="text-cream/50">{Math.round(w.mastery * 100)}%</span>
                      </div>
                      <ProgressBar value={w.mastery} className="mt-1" tone="gold" />
                    </div>
                  ))}
                </div>
              </Card>

              <Card>
                <CardTitle>Recent mistakes</CardTitle>
                <div className="mt-4 space-y-3">
                  {data.recent_mistakes.length === 0 && <p className="text-sm text-cream/40">No mistakes logged yet.</p>}
                  {data.recent_mistakes.map((m) => (
                    <div key={m.category} className="flex items-center justify-between rounded-xl border border-white/5 p-3">
                      <div>
                        <p className="text-sm capitalize text-cream/80">{m.category.replace("_", " ")}</p>
                        <p className="text-xs text-cream/40">{m.occurrence_count} occurrences · {formatRelativeTime(m.last_seen_at)}</p>
                      </div>
                      <Badge tone={m.trend === "improving" ? "cyan" : m.trend === "worsening" ? "red" : "neutral"}>{m.trend}</Badge>
                    </div>
                  ))}
                </div>
                <Link href="/mistakes" className="mt-4 inline-block text-xs text-cyan-400 hover:underline">View your full learning memory →</Link>
              </Card>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
