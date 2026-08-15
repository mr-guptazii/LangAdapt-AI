import { Badge } from "@/components/ui/Badge";

export interface SpeechMetrics {
  word_count: number;
  speaking_rate_wpm: number | null;
  pause_count: number;
  filler_word_count: number;
  repeated_word_count: number;
  fluency_score: number | null;
  speaking_score: number | null;
  sentence_completion_ratio: number;
}

export interface PronunciationInfo {
  overall_score: number;
  is_estimated: boolean;
  provider: string;
}

/** Renders real computed speech metrics. Pronunciation is always labeled when
 * it's an estimate (section 20) — never presented as if it were a precise
 * phoneme-level score. */
export function SpeechFeedbackCard({
  metrics, pronunciation, isMock,
}: { metrics: SpeechMetrics; pronunciation: PronunciationInfo | null; isMock: boolean }) {
  return (
    <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-3 text-xs">
      {isMock && (
        <p className="mb-2 text-cream/40">
          Mock transcription — configure <code>STT_PROVIDER=openai_whisper</code> and an API key for real speech-to-text.
        </p>
      )}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-4">
        <Metric label="Speaking" value={metrics.speaking_score} />
        <Metric label="Fluency" value={metrics.fluency_score} />
        <Metric
          label="Pronunciation"
          value={pronunciation?.overall_score ?? null}
          badge={pronunciation?.is_estimated ? "estimated" : undefined}
        />
        <Metric label="Pace" value={metrics.speaking_rate_wpm} suffix=" wpm" noScoreColor />
      </div>
      <div className="mt-2 flex flex-wrap gap-2 text-cream/50">
        <span>{metrics.pause_count} pause{metrics.pause_count === 1 ? "" : "s"}</span>
        <span>{metrics.filler_word_count} filler word{metrics.filler_word_count === 1 ? "" : "s"}</span>
        <span>{metrics.repeated_word_count} repeated word{metrics.repeated_word_count === 1 ? "" : "s"}</span>
      </div>
    </div>
  );
}

function Metric({ label, value, suffix = "", badge, noScoreColor }: { label: string; value: number | null; suffix?: string; badge?: string; noScoreColor?: boolean }) {
  const tone = noScoreColor || value === null ? "text-cream" : value >= 75 ? "text-cyan-300" : value >= 50 ? "text-gold-300" : "text-red-300";
  return (
    <div>
      <div className="flex items-center gap-1">
        <span className="text-cream/40">{label}</span>
        {badge && <Badge tone="neutral" className="px-1.5 py-0 text-[10px]">{badge}</Badge>}
      </div>
      <p className={`font-medium ${tone}`}>{value === null ? "—" : `${value}${suffix}`}</p>
    </div>
  );
}
