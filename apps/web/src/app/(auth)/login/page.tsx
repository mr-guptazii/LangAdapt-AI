"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { useAuthStore } from "@/stores/authStore";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState("demo@lingoadapt.ai");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const me = await login(email, password);
      router.push(me.onboarding_completed ? "/dashboard" : "/onboarding");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to log in.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-navy-950 px-6">
      <div className="pointer-events-none absolute inset-0 bg-grid-fade" />
      <Card className="relative w-full max-w-sm">
        <h1 className="font-display text-2xl text-gold-400">Welcome back</h1>
        <p className="mt-1 text-sm text-cream/60">Log in to continue where you left off.</p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div>
            <label className="mb-1 block text-xs text-cream/50" htmlFor="email">Email</label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="mb-1 block text-xs text-cream/50" htmlFor="password">Password</label>
            <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          {error && <p className="text-sm text-red-300">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>{loading ? "Logging in…" : "Log in"}</Button>
        </form>

        <p className="mt-4 text-center text-xs text-cream/40">
          Demo account prefilled: demo@lingoadapt.ai / demo1234
        </p>
        <p className="mt-6 text-center text-sm text-cream/60">
          No account? <Link href="/register" className="text-cyan-400 hover:underline">Sign up</Link>
        </p>
        <p className="mt-2 text-center text-xs">
          <Link href="/forgot-password" className="text-cream/40 hover:underline">Forgot password?</Link>
        </p>
      </Card>
    </main>
  );
}
