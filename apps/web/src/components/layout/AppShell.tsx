"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import {
  LayoutDashboard, MessageCircle, Dumbbell, TrendingUp, AlertCircle, BookMarked, Settings, LogOut, ShieldCheck,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/tutor", label: "AI Tutor", icon: MessageCircle },
  { href: "/practice", label: "Practice", icon: Dumbbell },
  { href: "/progress", label: "Progress", icon: TrendingUp },
  { href: "/mistakes", label: "Mistakes", icon: AlertCircle },
  { href: "/vocabulary", label: "Vocabulary", icon: BookMarked },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, hydrate, logout } = useAuthStore();

  useEffect(() => {
    hydrate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return <div className="flex min-h-screen items-center justify-center bg-navy-950 text-cream/50">Loading…</div>;
  }

  return (
    <div className="relative flex min-h-screen bg-navy-950">
      {/* Decorative only: bg-grid-fade's mask-image must never sit on an element
          that also contains real content, or it fades the content itself along
          with the grid pattern (see git history for the bug this caused). */}
      <div className="pointer-events-none absolute inset-0 bg-grid-fade" />
      <aside className="relative hidden w-60 shrink-0 flex-col border-r border-white/5 p-4 sm:flex">
        <span className="px-2 font-display text-lg text-gold-400">LingoAdapt</span>
        <nav className="mt-8 flex flex-1 flex-col gap-1">
          {NAV.map((item) => {
            const active = pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
                  active ? "bg-cyan-500/10 text-cyan-400" : "text-cream/60 hover:bg-white/5 hover:text-cream"
                )}
              >
                <item.icon size={18} />
                {item.label}
              </Link>
            );
          })}
          {user.is_admin && (
            <Link
              href="/admin"
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
                pathname?.startsWith("/admin") ? "bg-gold-500/10 text-gold-400" : "text-cream/60 hover:bg-white/5 hover:text-cream"
              )}
            >
              <ShieldCheck size={18} /> Admin
            </Link>
          )}
        </nav>
        <button
          onClick={() => { logout(); router.push("/login"); }}
          className="focus-ring flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-cream/50 hover:bg-white/5 hover:text-cream"
        >
          <LogOut size={18} /> Log out
        </button>
      </aside>
      <main className="relative flex-1 overflow-y-auto p-4 sm:p-8">{children}</main>
    </div>
  );
}
