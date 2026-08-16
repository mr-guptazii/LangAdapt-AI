"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { api, ApiError } from "@/lib/api";

function ResetPasswordForm() {
  const token = useSearchParams().get("token") ?? "";
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const newPassword = (new FormData(e.currentTarget).get("new_password") as string) ?? "";
    try {
      await api.post("/api/v1/auth/reset-password", { token, new_password: newPassword });
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That reset link is invalid or has expired.");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <p className="mt-6 rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-200">
        This link is missing its reset token. Use the link support gave you, or request a new one.
      </p>
    );
  }

  if (done) {
    return (
      <p className="mt-6 rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-4 text-sm text-cyan-200">
        Password reset — you can now <Link href="/login" className="underline">log in</Link> with your new password.
      </p>
    );
  }

  return (
    <form onSubmit={onSubmit} className="mt-6 space-y-4">
      <div>
        <label className="mb-1 block text-xs text-cream/50" htmlFor="new_password">New password</label>
        <Input id="new_password" name="new_password" type="password" minLength={8} required />
      </div>
      {error && <p className="text-sm text-red-300">{error}</p>}
      <Button type="submit" className="w-full" disabled={loading}>{loading ? "Resetting…" : "Reset password"}</Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-navy-950 px-6">
      <div className="pointer-events-none absolute inset-0 bg-grid-fade" />
      <Card className="relative w-full max-w-sm">
        <h1 className="font-display text-2xl text-gold-400">Set a new password</h1>
        <p className="mt-1 text-sm text-cream/60">Enter the password you&apos;d like to use going forward.</p>
        <Suspense>
          <ResetPasswordForm />
        </Suspense>
      </Card>
    </main>
  );
}
