"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardTitle } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { api } from "@/lib/api";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Line, LineChart,
} from "recharts";

interface MasteryRow { skill_code: string; skill_name: string; category: string; mastery: number; attempts: number; }
interface TrendRow { date: string; accuracy: number; }
interface ActivitySummary {
  daily_counts: { date: string; count: number }[];
  event_breakdown: { event_type: string; count: number }[];
}

export default function ProgressPage() {
  const [mastery, setMastery] = useState<MasteryRow[]>([]);
  const [trend, setTrend] = useState<TrendRow[]>([]);
  const [activity, setActivity] = useState<ActivitySummary | null>(null);

  useEffect(() => {
    api.get<MasteryRow[]>("/api/v1/progress/mastery").then(setMastery).catch(() => {});
    api.get<TrendRow[]>("/api/v1/progress/accuracy-trend").then(setTrend).catch(() => {});
    api.get<ActivitySummary>("/api/v1/progress/activity").then(setActivity).catch(() => {});
  }, []);

  const byCategory = mastery.reduce<Record<string, MasteryRow[]>>((acc, m) => {
    (acc[m.category] ??= []).push(m);
    return acc;
  }, {});

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
        <h1 className="font-display text-2xl text-gold-400">Your progress</h1>
        <p className="mt-1 text-sm text-cream/60">Every number here comes from real sessions and attempts.</p>

        <Card className="mt-6">
          <CardTitle>Weekly activity</CardTitle>
          <div className="mt-4 h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={activity?.daily_counts ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="date" tick={{ fill: "#f4ecd899", fontSize: 10 }} />
                <YAxis tick={{ fill: "#f4ecd899", fontSize: 11 }} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "#0f1524", border: "1px solid rgba(94,234,212,0.2)", borderRadius: 8 }} />
                <Bar dataKey="count" fill="#2dd4bf" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            {(!activity || activity.daily_counts.length === 0) && <p className="text-center text-sm text-cream/30">No activity recorded yet.</p>}
          </div>
        </Card>

        <Card className="mt-6">
          <CardTitle>Practice accuracy (last 14 days)</CardTitle>
          <div className="mt-4 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="date" tick={{ fill: "#f4ecd899", fontSize: 11 }} />
                <YAxis domain={[0, 1]} tick={{ fill: "#f4ecd899", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#0f1524", border: "1px solid rgba(94,234,212,0.2)", borderRadius: 8 }} />
                <Line type="monotone" dataKey="accuracy" stroke="#2dd4bf" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
            {trend.length === 0 && <p className="text-center text-sm text-cream/30">No practice attempts yet.</p>}
          </div>
        </Card>

        <div className="mt-6 grid gap-6 sm:grid-cols-2">
          {Object.entries(byCategory).map(([category, rows]) => (
            <Card key={category}>
              <CardTitle className="capitalize">{category}</CardTitle>
              <div className="mt-4 space-y-3">
                {rows.map((r) => (
                  <div key={r.skill_code}>
                    <div className="flex justify-between text-sm">
                      <span className="text-cream/80">{r.skill_name}</span>
                      <span className="text-cream/50">{Math.round(r.mastery * 100)}%</span>
                    </div>
                    <ProgressBar value={r.mastery} className="mt-1" />
                  </div>
                ))}
              </div>
            </Card>
          ))}
          {mastery.length === 0 && <p className="text-sm text-cream/40">No skills tracked yet — start a conversation or practice session.</p>}
        </div>

        {mastery.length > 0 && (
          <Card className="mt-6">
            <CardTitle>Mastery by skill</CardTitle>
            <div className="mt-4 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={mastery}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="skill_code" tick={{ fill: "#f4ecd899", fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={60} />
                  <YAxis domain={[0, 1]} tick={{ fill: "#f4ecd899", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#0f1524", border: "1px solid rgba(94,234,212,0.2)", borderRadius: 8 }} />
                  <Bar dataKey="mastery" fill="#eec267" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
