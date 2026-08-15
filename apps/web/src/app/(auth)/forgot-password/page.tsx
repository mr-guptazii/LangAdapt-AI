"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-navy-950 px-6">
      <div className="pointer-events-none absolute inset-0 bg-grid-fade" />
      <Card className="relative w-full max-w-sm">
        <h1 className="font-display text-2xl text-gold-400">Reset your password</h1>
        <p className="mt-1 text-sm text-cream/60">We&apos;ll email you a reset link.</p>

        {sent ? (
          <p className="mt-6 rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-4 text-sm text-cyan-200">
            If an account exists for that email, a reset link is on its way.
          </p>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setSent(true);
            }}
            className="mt-6 space-y-4"
          >
            <div>
              <label className="mb-1 block text-xs text-cream/50" htmlFor="email">Email</label>
              <Input id="email" type="email" required />
            </div>
            <Button type="submit" className="w-full">Send reset link</Button>
          </form>
        )}

        <p className="mt-6 text-center text-sm text-cream/60">
          <Link href="/login" className="text-cyan-400 hover:underline">Back to log in</Link>
        </p>
      </Card>
    </main>
  );
}
