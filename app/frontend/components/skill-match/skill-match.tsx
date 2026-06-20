"use client";

import * as React from "react";
import { FileText, Loader2, Play, ScrollText } from "lucide-react";

import { Dropzone } from "@/components/project/dropzone";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { extractPaper, routePaper, SAMPLE_TEXT } from "@/lib/skill-match/api";
import type { ExtractResult, FeasibilityMap } from "@/lib/skill-match/types";
import { cn } from "@/lib/cn";
import { MetadataCard } from "./metadata-card";
import { SkillMatchResults } from "./skill-match-results";

type Phase = "idle" | "extracting" | "routing";

/**
 * The Skill-Match orchestrator. Drop a paper PDF → its metadata appears up top and the dropzone
 * becomes an inline PDF viewer (the browser renders the dropped file — no upload), so you read the
 * paper beside the matched skills. Hit Run → the deterministic router genuinely routes the extracted
 * text and the skills stream into the right column with a staggered reveal. Paste-text is the
 * offline fallback (no viewer).
 */
export function SkillMatch() {
  const [mode, setMode] = React.useState<"drop" | "paste">("drop");
  const [result, setResult] = React.useState<ExtractResult | null>(null);
  const [text, setText] = React.useState("");
  const [fileUrl, setFileUrl] = React.useState<string | null>(null); // object URL for the inline viewer
  const [map, setMap] = React.useState<FeasibilityMap | null>(null);
  const [phase, setPhase] = React.useState<Phase>("idle");
  const [error, setError] = React.useState<string | null>(null);

  const busy = phase !== "idle";

  // Revoke the object URL when it changes or on unmount (no leaked blobs).
  React.useEffect(() => {
    return () => {
      if (fileUrl) URL.revokeObjectURL(fileUrl);
    };
  }, [fileUrl]);

  async function onFile(file: File) {
    setPhase("extracting");
    setError(null);
    setMap(null);
    setFileUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
    try {
      const r = await extractPaper(file);
      setResult(r);
      setText(r.text);
    } catch {
      setError("Couldn't read that PDF. Is the backend running on :8000?");
      setResult(null);
      setText("");
    } finally {
      setPhase("idle");
    }
  }

  function reset() {
    setFileUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    setResult(null);
    setText("");
    setMap(null);
    setError(null);
    setMode("drop");
  }

  async function run() {
    if (!text.trim()) return;
    setPhase("routing");
    setError(null);
    try {
      setMap(await routePaper(text, result?.filename || "pasted"));
    } catch {
      setError("Couldn't reach the router. Is the backend running on :8000?");
      setMap(null);
    } finally {
      setPhase("idle");
    }
  }

  const hasPaper = !!fileUrl;

  return (
    <div className="space-y-6">
      {result && <MetadataCard result={result} />}

      {/* Once a PDF is loaded the route becomes a fixed-height two-pane row: the viewer is favoured
          (1.6fr) and gets the page's full width, and the skills column scrolls within itself so both
          panes stay exactly the same height and the paper reads beside the routing. */}
      <div
        className={cn(
          "grid gap-6",
          hasPaper ? "lg:h-[78vh] lg:grid-cols-[1.6fr_1fr]" : "lg:grid-cols-[minmax(0,22rem)_1fr]",
        )}
      >
        {/* Left — input / PDF viewer */}
        <div className={cn("flex min-h-0 flex-col gap-3", hasPaper && "lg:h-full")}>
          {hasPaper ? (
            <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="flex shrink-0 items-center gap-2 border-b border-border p-2.5">
                <Button onClick={run} disabled={busy || !text.trim()} size="sm">
                  {phase === "routing" ? <Loader2 className="animate-spin" /> : <Play />}
                  Run
                </Button>
                <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground" title={result?.filename}>
                  {result?.filename ?? "paper.pdf"}
                </span>
                <Button onClick={reset} disabled={busy} variant="ghost" size="sm">
                  Replace
                </Button>
              </div>
              <iframe
                src={fileUrl}
                title="Paper PDF"
                className="min-h-0 w-full flex-1 bg-muted"
              />
            </Card>
          ) : mode === "drop" ? (
            <>
              <Dropzone
                onFile={onFile}
                accept=".pdf,application/pdf"
                title="Drop a paper PDF"
                hint="or click to browse — we read the text layer, no upload stored"
                formats="PDF"
                icon={FileText}
                className="py-20"
              />
              <p className="text-center text-xs text-muted-foreground">
                or{" "}
                <button type="button" className="text-primary hover:underline" onClick={() => setMode("paste")}>
                  paste text instead
                </button>
              </p>
            </>
          ) : (
            <Card className="p-4">
              <label htmlFor="paper-text" className="text-sm font-medium text-foreground">
                Paste paper text
              </label>
              <p className="mt-0.5 text-xs text-muted-foreground">Methods + Figure legends.</p>
              <textarea
                id="paper-text"
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                  setResult(null);
                }}
                rows={12}
                spellCheck={false}
                placeholder={"Methods\n…\nFigure legends\nFigure 1. …"}
                className="mt-2 w-full resize-y rounded-md border border-input bg-background p-3 font-mono text-xs leading-relaxed text-foreground placeholder:text-muted-foreground/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <div className="mt-2 flex items-center justify-between">
                <button type="button" className="text-xs text-primary hover:underline" onClick={() => setText(SAMPLE_TEXT)}>
                  Try a sample
                </button>
                <button type="button" className="text-xs text-primary hover:underline" onClick={() => setMode("drop")}>
                  or drop a PDF
                </button>
              </div>
            </Card>
          )}

          {/* Run + status live below the input when there's no inline viewer (paste / pre-drop). */}
          {!hasPaper && (
            <Button onClick={run} disabled={busy || !text.trim()} className="w-full">
              {phase === "routing" ? <Loader2 className="animate-spin" /> : <Play />}
              Run
            </Button>
          )}
          {phase === "extracting" && (
            <p className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              Reading the PDF…
            </p>
          )}
          {error && (
            <p role="alert" className="text-center text-xs text-destructive">
              {error}
            </p>
          )}
          <p className="text-center text-[11px] text-muted-foreground">Deterministic · no LLM · offline</p>
        </div>

        {/* Right — matched skills (stream in on Run). When a paper is loaded this column scrolls as a
            whole so it matches the viewer's height instead of running past the fold. */}
        <div className={cn(hasPaper && "lg:h-full lg:min-h-0 lg:overflow-y-auto lg:pr-1")}>
          {map ? (
            <SkillMatchResults map={map} />
          ) : (
            <div className="flex h-full min-h-[18rem] flex-col items-center justify-center rounded-xl border border-dashed border-border py-16 text-center">
              <ScrollText className="size-8 text-muted-foreground/50" />
              <p className="mt-3 max-w-xs text-sm text-muted-foreground">
                Drop a paper and hit <span className="text-foreground">Run</span> to see which Selom
                skills each figure needs.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
