"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    const email = (new FormData(e.currentTarget).get("email") as string) ?? "";
    try {
      // Real request — creates a genuine, securely-hashed reset token
      // server-side. The response is deliberately identical whether or not
      // the account exists, so this can never be used to check which emails
      // have accounts.
      await api.post("/api/v1/auth/forgot-password", { email });
    } finally {
      setLoading(false);
      setSent(true);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-navy-950 px-6">
      <div className="pointer-events-none absolute inset-0 bg-grid-fade" />
      <Card className="relative w-full max-w-sm">
        <h1 className="font-display text-2xl text-gold-400">Reset your password</h1>
        <p className="mt-1 text-sm text-cream/60">
          Automatic email delivery for password resets isn&apos;t set up yet — a request is recorded, but you&apos;ll need to contact support to complete the reset for now.
        </p>

        {sent ? (
          <p className="mt-6 rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-4 text-sm text-cyan-200">
            If an account exists for that email, a reset has been started. Since we can&apos;t email you a link yet, please contact support with the email you used so we can complete it for you.
          </p>
        ) : (
          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <label className="mb-1 block text-xs text-cream/50" htmlFor="email">Email</label>
              <Input id="email" name="email" type="email" required />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>{loading ? "Sending…" : "Start password reset"}</Button>
          </form>
        )}

        <p className="mt-6 text-center text-sm text-cream/60">
          <Link href="/login" className="text-cyan-400 hover:underline">Back to log in</Link>
        </p>
      </Card>
    </main>
  );
}
