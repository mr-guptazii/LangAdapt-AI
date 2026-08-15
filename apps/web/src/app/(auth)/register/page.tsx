"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { useAuthStore } from "@/stores/authStore";
import { ApiError } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const register = useAuthStore((s) => s.register);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      await register(email, password, fullName || undefined);
      router.push("/onboarding");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create an account.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-navy-950 px-6">
      <div className="pointer-events-none absolute inset-0 bg-grid-fade" />
      <Card className="relative w-full max-w-sm">
        <h1 className="font-display text-2xl text-gold-400">Create your account</h1>
        <p className="mt-1 text-sm text-cream/60">Start with a short placement assessment.</p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div>
            <label className="mb-1 block text-xs text-cream/50" htmlFor="name">Full name</label>
            <Input id="name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-cream/50" htmlFor="email">Email</label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="mb-1 block text-xs text-cream/50" htmlFor="password">Password</label>
            <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
          </div>
          {error && <p className="text-sm text-red-300">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>{loading ? "Creating account…" : "Create account"}</Button>
        </form>

        <p className="mt-6 text-center text-sm text-cream/60">
          Already have an account? <Link href="/login" className="text-cyan-400 hover:underline">Log in</Link>
        </p>
      </Card>
    </main>
  );
}
