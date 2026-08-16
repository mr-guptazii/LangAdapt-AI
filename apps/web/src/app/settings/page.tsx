"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";

interface Settings {
  ai_personality: string; correction_style: string; voice_speed: number; interests: string[];
  store_raw_audio: boolean; personalization_enabled: boolean; analytics_enabled: boolean;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const { push } = useToast();

  useEffect(() => {
    api.get<Settings>("/api/v1/settings").then(setSettings).catch(() => {});
  }, []);

  async function save() {
    if (!settings) return;
    await api.patch("/api/v1/settings", settings);
    push("Settings saved.", "success");
  }

  async function exportData() {
    // A real, immediate download — not a promise of an email that no email
    // integration in this app can actually send.
    const data = await api.post("/api/v1/settings/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "lingoadapt-export.json";
    link.click();
    URL.revokeObjectURL(url);
    push("Your data has been downloaded.", "success");
  }

  async function deleteAccount() {
    if (!confirm("This permanently deletes your account and all your learning data — conversations, errors, vocabulary, and progress. This cannot be undone. Continue?")) return;
    await api.del("/api/v1/settings/account");
    push("Account and all associated data permanently deleted.", "info");
  }

  if (!settings) return <AppShell><p className="text-cream/40">Loading settings…</p></AppShell>;

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="font-display text-2xl text-gold-400">Settings</h1>

        <Card>
          <CardTitle>AI tutor personality</CardTitle>
          <select value={settings.ai_personality} onChange={(e) => setSettings({ ...settings, ai_personality: e.target.value })}
            className="focus-ring mt-3 w-full rounded-xl border border-white/10 bg-navy-800/60 px-3 py-2 text-sm text-cream">
            {["friendly", "professional", "strict_coach", "encouraging", "casual", "minimalist"].map((p) => (
              <option key={p} value={p}>{p.replace("_", " ")}</option>
            ))}
          </select>
        </Card>

        <Card>
          <CardTitle>Correction style</CardTitle>
          <select value={settings.correction_style} onChange={(e) => setSettings({ ...settings, correction_style: e.target.value })}
            className="focus-ring mt-3 w-full rounded-xl border border-white/10 bg-navy-800/60 px-3 py-2 text-sm text-cream">
            {["gentle", "balanced", "strict", "explain_all", "minimal"].map((c) => (
              <option key={c} value={c}>{c.replace("_", " ")}</option>
            ))}
          </select>
        </Card>

        <Card>
          <CardTitle>Voice speed</CardTitle>
          <input type="range" min={0.5} max={1.5} step={0.1} value={settings.voice_speed}
            onChange={(e) => setSettings({ ...settings, voice_speed: parseFloat(e.target.value) })}
            className="mt-3 w-full accent-cyan-500" />
          <p className="mt-1 text-xs text-cream/40">{settings.voice_speed.toFixed(1)}x</p>
        </Card>

        <Card>
          <CardTitle>Privacy</CardTitle>
          <div className="mt-3 space-y-3 text-sm">
            {([
              ["personalization_enabled", "Personalization"],
              ["analytics_enabled", "Usage analytics"],
              ["store_raw_audio", "Store raw voice recordings"],
            ] as const).map(([key, label]) => (
              <label key={key} className="flex items-center justify-between">
                <span className="text-cream/70">{label}</span>
                <input type="checkbox" checked={settings[key]} onChange={(e) => setSettings({ ...settings, [key]: e.target.checked })} className="accent-cyan-500" />
              </label>
            ))}
          </div>
        </Card>

        <Button onClick={save}>Save settings</Button>

        <Card>
          <CardTitle>Data</CardTitle>
          <div className="mt-3 flex gap-3">
            <Button variant="secondary" size="sm" onClick={exportData}>Export my data</Button>
            <Button variant="danger" size="sm" onClick={deleteAccount}>Delete account</Button>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
