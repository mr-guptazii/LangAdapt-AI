import { cn } from "@/lib/utils";

export function ProgressBar({ value, className, tone = "cyan" }: { value: number; className?: string; tone?: "cyan" | "gold" }) {
  const pct = Math.max(0, Math.min(100, value * 100));
  return (
    <div className={cn("h-2 w-full rounded-full bg-white/5 overflow-hidden", className)}>
      <div
        className={cn("h-full rounded-full transition-all duration-500", tone === "cyan" ? "bg-cyan-500" : "bg-gold-500")}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
