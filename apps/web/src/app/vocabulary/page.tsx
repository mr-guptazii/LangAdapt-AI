"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { Volume2, RotateCw } from "lucide-react";

interface VocabItem {
  id: string; word: string; translation: string; part_of_speech: string | null;
  example_sentence: string | null; status: string; next_review_at: string | null;
}

const STATUS_TONE: Record<string, "cyan" | "gold" | "neutral" | "red"> = {
  mastered: "cyan", active: "gold", learning: "neutral", forgotten: "red",
};

export default function VocabularyPage() {
  const [items, setItems] = useState<VocabItem[]>([]);
  const [flashcardMode, setFlashcardMode] = useState(false);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [filter, setFilter] = useState<string | null>(null);

  useEffect(() => {
    api.get<VocabItem[]>(`/api/v1/vocabulary${filter ? `?status_filter=${filter}` : ""}`).then(setItems).catch(() => {});
  }, [filter]);

  async function review(correct: boolean) {
    const item = items[index];
    if (!item) return;
    await api.post("/api/v1/vocabulary/review", { vocabulary_item_id: item.id, recalled_correctly: correct, response_time_ms: 3000 });
    setRevealed(false);
    setIndex((i) => Math.min(i + 1, items.length - 1));
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <div className="flex items-center justify-between">
          <h1 className="font-display text-2xl text-gold-400">Vocabulary</h1>
          <Button size="sm" variant="secondary" onClick={() => { setFlashcardMode((v) => !v); setIndex(0); setRevealed(false); }}>
            <RotateCw size={14} /> {flashcardMode ? "List view" : "Flashcard mode"}
          </Button>
        </div>

        {!flashcardMode && (
          <>
            <div className="mt-4 flex gap-2">
              {["all", "learning", "active", "mastered"].map((s) => (
                <button key={s} onClick={() => setFilter(s === "all" ? null : s)}
                  className={`rounded-lg border px-3 py-1 text-xs capitalize ${(filter ?? "all") === s ? "border-cyan-500 bg-cyan-500/10 text-cyan-300" : "border-white/10 text-cream/50"}`}>
                  {s}
                </button>
              ))}
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {items.map((v) => (
                <Card key={v.id} className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-cream">{v.word}</span>
                      {v.part_of_speech && <span className="text-xs text-cream/40">{v.part_of_speech}</span>}
                      <Volume2 size={13} className="text-cream/30" />
                    </div>
                    <p className="mt-0.5 text-sm text-cream/60">{v.translation}</p>
                    {v.example_sentence && <p className="mt-1 text-xs italic text-cream/40">&ldquo;{v.example_sentence}&rdquo;</p>}
                  </div>
                  <Badge tone={STATUS_TONE[v.status] ?? "neutral"}>{v.status}</Badge>
                </Card>
              ))}
              {items.length === 0 && <p className="text-sm text-cream/40">No vocabulary tracked yet.</p>}
            </div>
          </>
        )}

        {flashcardMode && items[index] && (
          <Card className="mx-auto mt-8 max-w-sm text-center">
            <p className="text-xs uppercase tracking-wide text-cream/40">Card {index + 1} of {items.length}</p>
            <button onClick={() => setRevealed((r) => !r)} className="mt-6 block w-full">
              <p className="font-display text-3xl text-gold-400">{items[index]?.word}</p>
              {revealed && (
                <>
                  <p className="mt-3 text-cream/70">{items[index]?.translation}</p>
                  {items[index]?.example_sentence && <p className="mt-2 text-xs italic text-cream/40">&ldquo;{items[index]?.example_sentence}&rdquo;</p>}
                </>
              )}
              {!revealed && <p className="mt-3 text-xs text-cream/30">Tap to reveal</p>}
            </button>
            {revealed && (
              <div className="mt-6 flex justify-center gap-3">
                <Button variant="danger" size="sm" onClick={() => review(false)}>Didn&apos;t know it</Button>
                <Button size="sm" onClick={() => review(true)}>Knew it</Button>
              </div>
            )}
          </Card>
        )}
        {flashcardMode && items.length === 0 && <p className="mt-8 text-center text-sm text-cream/40">No vocabulary to review.</p>}
      </div>
    </AppShell>
  );
}
