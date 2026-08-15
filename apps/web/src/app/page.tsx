"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  MessageCircle, Brain, Mic, Sparkles, TrendingUp, BookOpen, ArrowRight,
} from "lucide-react";

const FEATURES = [
  { icon: MessageCircle, title: "Real Conversations", desc: "Natural dialogue that adapts vocabulary, pace, and complexity to exactly where you are." },
  { icon: TrendingUp, title: "Adaptive Difficulty", desc: "A scoring engine reads your accuracy, streak, and confidence — and adjusts before you get bored or stuck." },
  { icon: Sparkles, title: "Context-Aware Corrections", desc: "Corrections arrive when they help, not every sentence — gentle, balanced, or strict, your call." },
  { icon: Brain, title: "Persistent Learning Memory", desc: "Recurring mistakes are remembered across sessions and turned into targeted practice automatically." },
  { icon: BookOpen, title: "Personalized Practice", desc: "Every exercise traces back to a real weakness or a review that's due — never a random quiz." },
  { icon: Mic, title: "Voice Tutor", desc: "Speak naturally and get feedback on fluency, grammar, and pronunciation, not just transcription." },
];

const STEPS = [
  { step: "01", title: "Take a placement assessment", desc: "An adaptive test estimates your CEFR level and maps your strengths and weaknesses." },
  { step: "02", title: "Talk, write, and practice", desc: "Every message runs through an agent graph: conversation, error analysis, learner modeling, adaptation." },
  { step: "03", title: "Watch the tutor adapt", desc: "Mastery scores update, memory accumulates, and your next lesson is chosen because of what just happened." },
];

export default function LandingPage() {
  return (
    <main className="relative overflow-x-hidden bg-navy-950">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[640px] bg-grid-fade" />
      <div className="pointer-events-none absolute -top-32 left-1/2 h-96 w-[720px] -translate-x-1/2 rounded-full bg-cyan-500/10 blur-[120px]" />

      <nav className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <span className="font-display text-xl text-gold-400">LingoAdapt <span className="text-cream/80">AI</span></span>
        <div className="flex items-center gap-3">
          <Link href="/login"><Button variant="ghost" size="sm">Log in</Button></Link>
          <Link href="/register"><Button size="sm">Get started</Button></Link>
        </div>
      </nav>

      <section className="relative z-10 mx-auto max-w-4xl px-6 pb-20 pt-16 text-center">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <span className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-500/5 px-4 py-1.5 text-xs text-cyan-400">
            <Sparkles size={14} /> An agentic AI tutor, not a chatbot
          </span>
          <h1 className="mt-6 font-display text-4xl leading-tight text-gold-400 sm:text-6xl">
            An AI language tutor that adapts to how <span className="italic text-gold-300">you</span> actually learn.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-cream/70">
            LingoAdapt observes your mistakes, models your proficiency, remembers what trips you up, and rebuilds
            every lesson around it — conversation, grammar, vocabulary, and voice, continuously adapted.
          </p>
          <div className="mt-8 flex items-center justify-center gap-4">
            <Link href="/register"><Button size="lg">Start learning free <ArrowRight size={18} /></Button></Link>
            <Link href="/login"><Button variant="secondary" size="lg">Try the demo account</Button></Link>
          </div>
        </motion.div>
      </section>

      <section className="relative z-10 mx-auto max-w-6xl px-6 py-16">
        <h2 className="text-center font-display text-2xl text-gold-400 sm:text-3xl">Built for real adaptation, not scripted lessons</h2>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <motion.div key={f.title} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }}>
              <Card className="h-full hover:border-cyan-500/30 transition-colors">
                <f.icon className="text-cyan-400" size={22} />
                <h3 className="mt-4 font-display text-lg text-cream">{f.title}</h3>
                <p className="mt-2 text-sm text-cream/60">{f.desc}</p>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="relative z-10 mx-auto max-w-5xl px-6 py-16">
        <h2 className="text-center font-display text-2xl text-gold-400 sm:text-3xl">How it works</h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.step} className="relative">
              <span className="font-display text-4xl text-cyan-500/30">{s.step}</span>
              <h3 className="mt-2 font-display text-lg text-cream">{s.title}</h3>
              <p className="mt-2 text-sm text-cream/60">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="relative z-10 mx-auto max-w-4xl px-6 py-20 text-center">
        <Card className="border-gold-500/20 shadow-glow-gold">
          <h2 className="font-display text-2xl text-gold-400 sm:text-3xl">Ready to have a tutor that remembers you?</h2>
          <p className="mx-auto mt-3 max-w-xl text-cream/60">
            Create an account, take a two-minute placement assessment, and start a conversation the AI will actually learn from.
          </p>
          <div className="mt-6">
            <Link href="/register"><Button size="lg">Create your free account</Button></Link>
          </div>
        </Card>
      </section>

      <footer className="relative z-10 border-t border-white/5 py-8 text-center text-xs text-cream/40">
        LingoAdapt AI — an agentic language-tutor architecture demo. Built with LangGraph, FastAPI, and Next.js.
      </footer>
    </main>
  );
}
