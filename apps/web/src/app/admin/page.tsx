"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import { Users, Activity, DollarSign, Database, Server } from "lucide-react";

interface Overview {
  total_users: number; active_users_7d: number; active_sessions: number;
  cefr_distribution: Record<string, number>; language_distribution: Record<string, number>;
}
interface AIUsage {
  period_days: number; total_calls: number; total_input_tokens: number; total_output_tokens: number;
  total_estimated_cost_usd: number; by_model: { model: string; provider: string; calls: number; estimated_cost_usd: number }[];
  by_node: { node: string; calls: number }[]; daily_cost_usd: { date: string; cost: number }[];
}
interface CommonError { category: string; learners_affected: number; total_occurrences: number; }
interface Retention { dau: number; wau: number; mau: number; dau_mau_ratio: number; }
interface SystemHealth {
  database: { healthy: boolean }; redis: { healthy: boolean; latency_ms: number | null };
  row_counts: Record<string, number>; note: string;
}

const COLORS = ["#2dd4bf", "#eec267", "#f4ecd8", "#5eead4", "#dba43e"];

export default function AdminPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [usage, setUsage] = useState<AIUsage | null>(null);
  const [errors, setErrors] = useState<CommonError[]>([]);
  const [retention, setRetention] = useState<Retention | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);

  useEffect(() => {
    if (user && !user.is_admin) router.replace("/dashboard");
  }, [user, router]);

  useEffect(() => {
    api.get<Overview>("/api/v1/analytics/admin/overview").then(setOverview).catch(() => {});
    api.get<AIUsage>("/api/v1/analytics/admin/ai-usage").then(setUsage).catch(() => {});
    api.get<CommonError[]>("/api/v1/analytics/admin/common-errors").then(setErrors).catch(() => {});
    api.get<Retention>("/api/v1/analytics/admin/retention").then(setRetention).catch(() => {});
    api.get<SystemHealth>("/api/v1/analytics/admin/system-health").then(setHealth).catch(() => {});
  }, []);

  if (user && !user.is_admin) return null;

  const languageData = overview ? Object.entries(overview.language_distribution).map(([name, value]) => ({ name, value })) : [];

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl">
        <h1 className="font-display text-2xl text-gold-400">Admin dashboard</h1>
        <p className="mt-1 text-sm text-cream/60">Aggregate metrics only — individual conversation content is never shown here.</p>

        <div className="mt-6 grid gap-4 sm:grid-cols-4">
          <Card className="flex items-center gap-3">
            <Users className="text-cyan-400" />
            <div>
              <p className="text-xs uppercase tracking-wide text-cream/40">Total users</p>
              <p className="font-display text-2xl text-cream">{overview?.total_users ?? "—"}</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3">
            <Activity className="text-gold-400" />
            <div>
              <p className="text-xs uppercase tracking-wide text-cream/40">Active sessions</p>
              <p className="font-display text-2xl text-cream">{overview?.active_sessions ?? "—"}</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3">
            <DollarSign className="text-cyan-400" />
            <div>
              <p className="text-xs uppercase tracking-wide text-cream/40">AI cost (30d)</p>
              <p className="font-display text-2xl text-cream">${usage?.total_estimated_cost_usd.toFixed(4) ?? "—"}</p>
            </div>
          </Card>
          <Card className="flex items-center gap-3">
            <Database className="text-gold-400" />
            <div>
              <p className="text-xs uppercase tracking-wide text-cream/40">AI calls (30d)</p>
              <p className="font-display text-2xl text-cream">{usage?.total_calls ?? "—"}</p>
            </div>
          </Card>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <Card>
            <CardTitle>System health</CardTitle>
            {health ? (
              <div className="mt-4 space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-cream/70"><Server size={14} /> Database</span>
                  <Badge tone={health.database.healthy ? "cyan" : "red"}>{health.database.healthy ? "healthy" : "down"}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-cream/70"><Server size={14} /> Redis</span>
                  <Badge tone={health.redis.healthy ? "cyan" : "red"}>
                    {health.redis.healthy ? `healthy (${health.redis.latency_ms}ms)` : "down"}
                  </Badge>
                </div>
                <div className="border-t border-white/5 pt-3">
                  <p className="text-xs text-cream/40">Row counts</p>
                  <div className="mt-1 grid grid-cols-2 gap-1 text-xs text-cream/60">
                    {Object.entries(health.row_counts).map(([k, v]) => (
                      <div key={k} className="flex justify-between"><span>{k}</span><span>{v}</span></div>
                    ))}
                  </div>
                </div>
                <p className="text-xs text-cream/30">{health.note}</p>
              </div>
            ) : <p className="mt-4 text-sm text-cream/40">Loading…</p>}
          </Card>

          <Card>
            <CardTitle>Retention</CardTitle>
            {retention ? (
              <div className="mt-4 grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="font-display text-3xl text-cyan-400">{retention.dau}</p>
                  <p className="text-xs text-cream/40">Daily active</p>
                </div>
                <div>
                  <p className="font-display text-3xl text-gold-400">{retention.wau}</p>
                  <p className="text-xs text-cream/40">Weekly active</p>
                </div>
                <div>
                  <p className="font-display text-3xl text-cream">{retention.mau}</p>
                  <p className="text-xs text-cream/40">Monthly active</p>
                </div>
              </div>
            ) : <p className="mt-4 text-sm text-cream/40">Loading…</p>}
            {overview && (
              <div className="mt-6">
                <p className="text-xs text-cream/40">Target language distribution</p>
                <div className="mt-2 h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={languageData} dataKey="value" nameKey="name" outerRadius={60} label>
                        {languageData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                      </Pie>
                      <Tooltip contentStyle={{ background: "#0f1524", border: "1px solid rgba(94,234,212,0.2)", borderRadius: 8 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </Card>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <Card>
            <CardTitle>AI usage by node</CardTitle>
            <div className="mt-4 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={usage?.by_node ?? []} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis type="number" tick={{ fill: "#f4ecd899", fontSize: 11 }} />
                  <YAxis type="category" dataKey="node" width={140} tick={{ fill: "#f4ecd899", fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: "#0f1524", border: "1px solid rgba(94,234,212,0.2)", borderRadius: 8 }} />
                  <Bar dataKey="calls" fill="#2dd4bf" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card>
            <CardTitle>Most common learner errors (all users)</CardTitle>
            <div className="mt-4 space-y-2">
              {errors.length === 0 && <p className="text-sm text-cream/40">No errors recorded yet.</p>}
              {errors.map((e) => (
                <div key={e.category} className="flex items-center justify-between rounded-xl border border-white/5 p-3 text-sm">
                  <span className="capitalize text-cream/80">{e.category.replace("_", " ")}</span>
                  <span className="text-xs text-cream/50">{e.learners_affected} learners · {e.total_occurrences} occurrences</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {overview && (
          <Card className="mt-6">
            <CardTitle>CEFR level distribution</CardTitle>
            <div className="mt-4 h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={Object.entries(overview.cefr_distribution).map(([level, count]) => ({ level, count }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="level" tick={{ fill: "#f4ecd899", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#f4ecd899", fontSize: 11 }} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: "#0f1524", border: "1px solid rgba(94,234,212,0.2)", borderRadius: 8 }} />
                  <Bar dataKey="count" fill="#eec267" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
