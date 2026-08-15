import { Sparkles } from "lucide-react";

interface Props {
  teachingStrategy?: string | null;
  difficultyDecision?: string | null;
  recommendedActivity?: { reason: string; target_skill_code: string } | null;
  agentsInvoked: string[];
}

/** Section 32 "Why this lesson?" — a safe, structured summary. Never shows raw
 * chain-of-thought, only the decision fields the agents actually returned. */
export function AgentDecisionCard({ teachingStrategy, difficultyDecision, recommendedActivity, agentsInvoked }: Props) {
  if (!teachingStrategy && !difficultyDecision && !recommendedActivity) return null;
  return (
    <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-3 text-xs text-cream/70">
      <div className="flex items-center gap-1.5 text-cyan-400">
        <Sparkles size={12} /> <span className="font-medium">AI decision trace</span>
      </div>
      <div className="mt-1.5 space-y-1">
        {difficultyDecision && <p>Difficulty: <span className="text-cream">{difficultyDecision.replace("_", " ")}</span></p>}
        {teachingStrategy && <p>Strategy: <span className="text-cream">{teachingStrategy.replace("_", " ")}</span></p>}
        {recommendedActivity && <p>Suggestion: <span className="text-cream">{recommendedActivity.reason}</span></p>}
        <p className="text-cream/30">Pipeline: {agentsInvoked.join(" → ")}</p>
      </div>
    </div>
  );
}
