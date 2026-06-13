"use client";

import * as React from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { type LucideIcon, UploadCloud } from "lucide-react";
import { cn } from "@/lib/cn";

/**
 * A prominent, obvious drag-and-drop target with clear state changes:
 *  - idle: dashed border, calm surface, "Drop … or click to browse"
 *  - mouse hover: border + surface lift (it reads as clickable)
 *  - file dragged over: solid cyan border, a soft glow fills the box, the icon
 *    springs up, a ring pulses out, and the copy switches to "Release to add it".
 *
 * Uses a drag-enter/leave COUNTER so moving the cursor over inner elements
 * doesn't flicker the state. Reduced-motion keeps every colour/border change but
 * drops the spring + pulse. It's a real <label> wrapping a file <input>, so click
 * and keyboard both work and it's announced correctly.
 */
export function Dropzone({
  onFile,
  accept,
  title,
  hint,
  formats,
  icon: Icon = UploadCloud,
  variant = "primary",
  className,
}: {
  onFile: (file: File) => void;
  accept: string;
  title: string;
  hint: string;
  formats?: string;
  icon?: LucideIcon;
  variant?: "primary" | "secondary";
  className?: string;
}) {
  const [dragging, setDragging] = React.useState(false);
  const counter = React.useRef(0);
  const reduce = useReducedMotion();
  const primary = variant === "primary";

  function reset() {
    counter.current = 0;
    setDragging(false);
  }

  return (
    <label
      onDragEnter={(e) => {
        e.preventDefault();
        counter.current += 1;
        setDragging(true);
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={(e) => {
        e.preventDefault();
        counter.current = Math.max(0, counter.current - 1);
        if (counter.current === 0) setDragging(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        reset();
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      className={cn(
        "group relative block cursor-pointer overflow-hidden rounded-2xl border border-dashed transition-colors duration-200",
        "focus-within:outline-none focus-within:ring-2 focus-within:ring-ring/50",
        dragging
          ? "border-primary bg-accent/30"
          : "border-input bg-card/40 hover:border-primary/50 hover:bg-card/70",
        primary ? "px-8 py-12" : "px-5 py-6",
        className,
      )}
    >
      <input
        type="file"
        accept={accept}
        aria-label={title}
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />

      {/* glow that fills the box while a file hovers */}
      <AnimatePresence>
        {dragging && !reduce && (
          <motion.div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="absolute left-1/2 top-1/2 h-[180%] w-[85%] -translate-x-1/2 -translate-y-1/2 glow-orb" />
          </motion.div>
        )}
      </AnimatePresence>

      <div className="relative flex flex-col items-center gap-3 text-center">
        <motion.span
          aria-hidden
          animate={reduce ? undefined : { scale: dragging ? 1.12 : 1, y: dragging ? -2 : 0 }}
          transition={{ type: "spring", stiffness: 420, damping: 22 }}
          className={cn(
            "relative grid place-items-center rounded-2xl border transition-colors",
            primary ? "size-16 [&_svg]:size-7" : "size-11 [&_svg]:size-5",
            dragging
              ? "border-primary/60 bg-[color-mix(in_oklab,var(--primary)_16%,var(--card))] text-primary"
              : "border-border bg-background/70 text-primary",
          )}
        >
          <Icon />
          {dragging && !reduce && (
            <motion.span
              aria-hidden
              className="absolute inset-0 rounded-2xl ring-2 ring-primary/50"
              initial={{ opacity: 0.7, scale: 1 }}
              animate={{ opacity: 0, scale: 1.55 }}
              transition={{ duration: 1, repeat: Infinity, ease: "easeOut" }}
            />
          )}
        </motion.span>

        <div>
          <p className={cn("font-semibold text-foreground", primary ? "text-lg" : "text-sm")}>
            {dragging ? "Release to add it" : title}
          </p>
          <p className={cn("mt-1 text-muted-foreground", primary ? "text-sm" : "text-xs")}>
            {dragging ? "Drop the file anywhere in this box" : hint}
          </p>
        </div>

        {formats && !dragging && (
          <p className="tabular text-xs text-muted-foreground/80">{formats}</p>
        )}
      </div>
    </label>
  );
}
