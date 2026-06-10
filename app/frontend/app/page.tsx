"use client";

import { useCallback, useEffect, useState } from "react";
import { TopBar } from "@/components/app/top-bar";
import { EditorWorkspace } from "@/components/figure/editor-workspace";
import { UploadHero } from "@/components/upload/upload-hero";
import { useFigureStore } from "@/hooks/use-figure-store";
import { runSkill } from "@/lib/skills-api";

type Status = "idle" | "running" | "error";

export default function Home() {
  const store = useFigureStore();
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string>();
  const [fileName, setFileName] = useState<string>();

  const handleFile = useCallback(
    async (file: File) => {
      setStatus("running");
      setError(undefined);
      setFileName(file.name);
      try {
        const figure = await runSkill("umap_scrna", file);
        store.init(figure);
        setStatus("idle");
      } catch (e) {
        setStatus("error");
        setError(e instanceof Error ? e.message : "Upload failed. Please try again.");
      }
    },
    [store],
  );

  const handleReset = useCallback(() => {
    store.reset();
    setStatus("idle");
    setError(undefined);
    setFileName(undefined);
  }, [store]);

  // Undo / redo keyboard shortcuts (Cmd/Ctrl+Z, Cmd/Ctrl+Shift+Z).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== "z") return;
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      e.preventDefault();
      if (e.shiftKey) store.redo();
      else store.undo();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [store]);

  const hasFigure = store.spec !== null;

  return (
    <div className="flex h-dvh flex-col">
      <TopBar store={store} fileName={fileName} hasFigure={hasFigure} onReset={handleReset} />
      {hasFigure ? (
        <EditorWorkspace store={store} />
      ) : (
        <UploadHero onFile={handleFile} status={status} error={error} fileName={fileName} />
      )}
    </div>
  );
}
