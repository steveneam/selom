"use client";

import { motion, useReducedMotion } from "motion/react";
import { FileText, ScanText, Sparkles } from "lucide-react";

/**
 * The Run → results transition. A deterministic-feeling pseudo progress sweep (no real percentage —
 * the router is fast and offline) that narrates the three stages of the keyword index as a glowing
 * Selom-cyan→violet bar fills left→right with a scanline, then hands off to the streamed results.
 * Reduced-motion gets a static, filled bar (no sweep, no shimmer).
 */
const STEPS = [
  { icon: FileText, label: "Reading methods" },
  { icon: ScanText, label: "Scanning captions" },
  { icon: Sparkles, label: "Matching skills" },
] as const;

export function RoutingProgress() {
  const reduce = useReducedMotion();
  return (
    <div className="flex h-full min-h-[18rem] flex-col items-center justify-center rounded-xl border border-border bg-card/40 py-16 text-center">
      <div className="w-full max-w-xs px-6">
        <div className="mb-4 flex items-start justify-between gap-2">
          {STEPS.map((s, i) => (
            <motion.div
              key={s.label}
              className="flex flex-1 flex-col items-center gap-1.5"
              initial={reduce ? false : { opacity: 0.3, y: 3 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: reduce ? 0 : i * 0.32, duration: 0.3, ease: "easeOut" }}
            >
              <span className="grid size-7 place-items-center rounded-full border border-primary/40 bg-primary/10 text-primary">
                <s.icon className="size-3.5" />
              </span>
              <span className="text-[10px] leading-tight text-muted-foreground">{s.label}</span>
            </motion.div>
          ))}
        </div>

        <div className="relative h-2 overflow-hidden rounded-full bg-muted">
          <motion.div
            className="absolute inset-y-0 left-0 rounded-full"
            style={{
              background: "linear-gradient(90deg, var(--primary), #a78bfa)",
              boxShadow: "0 0 12px -1px color-mix(in oklab, var(--primary) 70%, transparent)",
            }}
            initial={reduce ? { width: "100%" } : { width: "6%" }}
            animate={{ width: "100%" }}
            transition={{ duration: reduce ? 0 : 1.05, ease: [0.22, 1, 0.36, 1] }}
          />
          {!reduce && (
            <motion.div
              className="absolute inset-y-0 w-1/3"
              style={{
                background:
                  "linear-gradient(90deg, transparent, color-mix(in oklab, white 55%, transparent), transparent)",
              }}
              initial={{ x: "-120%" }}
              animate={{ x: "360%" }}
              transition={{ repeat: Infinity, duration: 0.95, ease: "linear" }}
            />
          )}
        </div>

        <p className="mt-3 text-xs text-muted-foreground">Routing figures to skills…</p>
      </div>
    </div>
  );
}
