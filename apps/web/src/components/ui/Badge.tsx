import { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: "cyan" | "gold" | "red" | "neutral";
}

const tones = {
  cyan: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  gold: "bg-gold-500/10 text-gold-400 border-gold-500/30",
  red: "bg-red-500/10 text-red-300 border-red-500/30",
  neutral: "bg-white/5 text-cream/70 border-white/10",
};

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium", tones[tone], className)}
      {...props}
    />
  );
}
