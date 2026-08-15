"use client";

import { motion } from "framer-motion";

/** Renders real rolling volume-level samples from the microphone (see
 * useVoiceRecorder) as animated bars — not a decorative fake animation. */
export function Waveform({ levels, active }: { levels: number[]; active: boolean }) {
  const bars = 24;
  const padded = Array.from({ length: bars }, (_, i) => {
    const idx = levels.length - bars + i;
    return idx >= 0 ? (levels[idx] ?? 0.04) : 0.04;
  });

  return (
    <div className="flex h-10 items-center justify-center gap-[3px]" role="img" aria-label="Microphone input level">
      {padded.map((level, i) => (
        <motion.span
          key={i}
          className={active ? "w-1 rounded-full bg-cyan-400" : "w-1 rounded-full bg-cream/20"}
          animate={{ height: `${Math.max(8, level * 100)}%` }}
          transition={{ duration: 0.1 }}
          style={{ height: "20%" }}
        />
      ))}
    </div>
  );
}
