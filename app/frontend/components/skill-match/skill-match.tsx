"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useReducedMotion } from "motion/react";
import { FileText, FlaskConical, Loader2, Play, ScrollText } from "lucide-react";

import { Dropzone } from "@/components/project/dropzone";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PaperPipeline } from "@/components/paper/pipeline";
import { PaperMetaHeader } from "@/components/paper/paper-meta-header";
import { extractPaper, routePaper, SAMPLE_TEXT, toSavedPaper } from "@/lib/skill-match/api";
import { workspaceStore } from "@/lib/workspace/store";
import type { ExtractResult, FeasibilityMap } from "@/lib/skill-match/types";
import { RoutingProgress } from "./routing-progress";
import { SkillMatchResults } from "./skill-match-results";

type Phase = "idle" | "extracting" | "routing";

/** The lead-in, shown only before a paper is loaded — once a PDF is in, the metadata card is the
 *  header instead (no need to keep re-explaining the surface). */
function Intro() {
  return (
    <div className="max-w-2xl">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary/80">Skill Keyword Index</p>
      <h1 className="text-display mt-3 text-3xl text-foreground sm:text-4xl">
        Which Selom skills does this <span className="accent-keyword">paper</span> need?
      </h1>
      <p className="mt-4 text-base leading-relaxed text-muted-foreground">
        Drop a paper PDF. A deterministic keyword index — no LLM on the path — reads its methods and
        figure captions, then matches each figure to a Selom skill or flags its modality as out of
        scope. The optional <span className="text-foreground">Pro AI</span> tier verifies the figures
        that routed with low confidence.
      </p>
    </div>
  );
}

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
  const reduce = useReducedMotion();
  const router = useRouter();

  // The pipeline's forward step (umbrella stage 1 → stage 2): save this match as the Paper anchor
  // (idempotent on doi||filename) and carry it into the Reproduction workspace — no re-drop.
  function handleReproduce() {
    if (!map) return;
    const saved = workspaceStore.savePaper(
      toSavedPaper(map, result?.metadata ?? null, result?.filename ?? "paper"),
    );
    router.push(`/paper/${saved.id}?stage=reproduce`);
  }

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
    setMap(null);
    // Hold the routing sweep on-screen for at least its animation so it reads as a deliberate pass,
    // not a flash (the router itself is near-instant). Reduced-motion barely waits.
    const minMs = reduce ? 300 : 1100;
    try {
      const [m] = await Promise.all([
        routePaper(text, result?.filename || "pasted"),
        new Promise((r) => setTimeout(r, minMs)),
      ]);
      setMap(m as FeasibilityMap);
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
      {/* Header swaps from the lead-in to the paper's metadata once a PDF is loaded — the layout
          shifts up, the explainer retires, and the record of what you dropped takes its place. The
          pipeline sits ABOVE the metadata so the Skill Match → Reproduce → Score workflow reads as
          one pipeline, with "Reproduce" as the forward step (enabled once the match has run). */}
      {hasPaper ? (
        result && (
          <>
            <PaperPipeline
              current="skill-match"
              forward={{
                label: "Reproduce",
                icon: FlaskConical,
                onClick: handleReproduce,
                disabled: !map,
                title: map
                  ? "Save this paper and open it in Reproduction to add supplementary data"
                  : "Run the match first, then carry the paper into Reproduction",
              }}
            />
            <PaperMetaHeader
              meta={
                result.metadata
                  ? { ...result.metadata, isPreprint: result.metadata.is_preprint }
                  : null
              }
              filename={result.filename}
            />
          </>
        )
      ) : (
        <Intro />
      )}

      {hasPaper ? (
        /* Paper loaded → a fixed-height two-pane row: the viewer is favoured (1.6fr) and gets the
           page's full width, and the skills column scrolls within itself so both panes stay exactly
           the same height. Run lives in the viewer's toolbar (never at the page bottom). */
        <div className="grid gap-6 lg:h-[78vh] lg:grid-cols-[1.6fr_1fr]">
          {/* Left — the inline PDF viewer */}
          <div className="flex min-h-0 flex-col gap-3 lg:h-full">
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
              <iframe src={fileUrl} title="Paper PDF" className="min-h-0 w-full flex-1 bg-muted" />
            </Card>
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
          </div>

          {/* Right — the routing sweep, then the matched skills; scrolls as a whole to match the viewer. */}
          <div className="lg:h-full lg:min-h-0 lg:overflow-y-auto lg:pr-1">
            {phase === "routing" ? (
              <RoutingProgress />
            ) : map ? (
              <SkillMatchResults
                map={map}
                meta={result?.metadata ?? null}
                filename={result?.filename ?? "paper"}
              />
            ) : (
              <div className="flex h-full min-h-[18rem] flex-col items-center justify-center rounded-xl border border-dashed border-border py-16 text-center">
                <ScrollText className="size-8 text-muted-foreground/50" />
                <p className="mt-3 max-w-xs text-sm text-muted-foreground">
                  Ready when you are — hit <span className="text-foreground">Run</span> to route this
                  paper&apos;s figures to Selom skills.
                </p>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* No paper yet → a single, centred input box. No second placeholder beside it, and no Run at
           the bottom in drop mode (Run only appears once it's needed: in the viewer, or under paste). */
        <div className="space-y-6">
          <div className="mx-auto w-full max-w-xl space-y-3">
            {mode === "drop" ? (
              <>
                <Dropzone
                  onFile={onFile}
                  accept=".pdf,application/pdf"
                  title="Drop a paper PDF"
                  hint="or click to browse — we read the text layer, no upload stored"
                  formats="PDF"
                  icon={FileText}
                  className="py-24"
                />
                <p className="text-center text-xs text-muted-foreground">
                  or{" "}
                  <button type="button" className="text-primary hover:underline" onClick={() => setMode("paste")}>
                    paste text instead
                  </button>
                </p>
              </>
            ) : (
              <>
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
                <Button onClick={run} disabled={busy || !text.trim()} className="w-full">
                  {phase === "routing" ? <Loader2 className="animate-spin" /> : <Play />}
                  Run
                </Button>
              </>
            )}
            {error && (
              <p role="alert" className="text-center text-xs text-destructive">
                {error}
              </p>
            )}
            <p className="text-center text-[11px] text-muted-foreground">Deterministic · no LLM · offline</p>
          </div>

          {/* Paste mode has no viewer to anchor results, so the sweep + skills stream below the input. */}
          {mode === "paste" && (phase === "routing" || map) && (
            <div className="mx-auto w-full max-w-3xl">
              {phase === "routing" ? (
                <RoutingProgress />
              ) : (
                map && (
                  <SkillMatchResults
                    map={map}
                    meta={result?.metadata ?? null}
                    filename={result?.filename ?? "pasted"}
                  />
                )
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
