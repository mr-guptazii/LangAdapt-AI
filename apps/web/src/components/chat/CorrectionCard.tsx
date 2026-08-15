import { Badge } from "@/components/ui/Badge";

interface Correction {
  type: string; category: string; incorrect: string; correct: string; severity: string; explanation: string;
}

export function CorrectionCard({ correction }: { correction: Correction }) {
  const tone = correction.severity === "high" ? "red" : correction.severity === "medium" ? "gold" : "neutral";
  return (
    <div className="rounded-xl border border-gold-500/20 bg-gold-500/5 p-3 text-sm">
      <div className="flex items-center gap-2">
        <Badge tone={tone as "red" | "gold" | "neutral"}>{correction.category.replace("_", " ")}</Badge>
        <span className="text-cream/40 line-through">{correction.incorrect}</span>
        <span className="text-cream/40">→</span>
        <span className="font-medium text-cyan-300">{correction.correct}</span>
      </div>
      <p className="mt-1.5 text-cream/60">{correction.explanation}</p>
    </div>
  );
}
