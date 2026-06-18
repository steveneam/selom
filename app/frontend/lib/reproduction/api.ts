"use client";

/**
 * Reproduction view data access (read-only, v1 internal dogfood — spec D12).
 *
 * Reads the live engine output through the /api proxy (GET /papers, GET /papers/{slug}),
 * falling back to the embedded real-data fixture when the backend is unreachable — the
 * same live-or-seed pattern as lib/catalog/registry.ts. The fixture is the SAME engine
 * output the backend serves, so the view is honest either way.
 */

import * as React from "react";

import { REPRO_LEDGERS, REPRO_PAPERS } from "./fixture";
import type { Attribution, Ledger, PaperSummary } from "./types";

const PAPERS_URL = "/api/papers";

/** Short display labels for the three dogfood papers (the long titles stay as subtitles). */
export const PAPER_SHORT: Record<string, string> = {
  rpgrip1: "RPGRIP1",
  jev: "JEV",
  hani: "Hani",
};

export function shortName(slug: string): string {
  return PAPER_SHORT[slug] ?? slug;
}

/** Human labels for the named tiers (the backend ships only the slug + hex color). */
export const TIER_LABELS: Record<string, string> = {
  verified: "Verified",
  reproduced: "Reproduced",
  recoverable: "Recoverable",
  "deposit-faithful": "Deposit-faithful",
  irreproducible: "Irreproducible",
  discrepant: "Discrepant",
  "out-of-scope": "Out of scope",
};

export function tierLabel(tier: string): string {
  return TIER_LABELS[tier] ?? tier;
}

/** What each attribution chip means (the icon comes from the backend per panel). */
export const ATTRIBUTION_META: Record<Attribution, { icon: string; label: string }> = {
  selom: { icon: "✓", label: "Selom-correct" },
  engine: { icon: "⚙", label: "Engine substitution" },
  paper: { icon: "📄", label: "Paper-side" },
  data: { icon: "🗄", label: "Data-side" },
};

/**
 * Resolve a staged panel thumbnail (`/repro-assets/...`, served by the backend) through the
 * `/api` proxy so it loads in dev and prod alike. Empty in, empty out.
 */
export function panelAssetUrl(thumbnailUrl: string | undefined | null): string {
  return thumbnailUrl ? `/api${thumbnailUrl}` : "";
}

/**
 * The in-paper "Digitize this panel" link: opens the chart-extractor on the lifted panel.
 * Carries the raw thumbnail path (the picker re-resolves it through the proxy), the panel
 * identity (for the not-scored banner), and the traceable form. Digitize ≠ reproduce — this
 * never feeds the score; the picker says so.
 */
export function digitizeHref(slug: string, panelKey: string, thumbnailUrl: string, form: string): string {
  const q = new URLSearchParams({ img: thumbnailUrl, panel: `${slug}:${panelKey}`, form });
  return `/extract?${q.toString()}`;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: { accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${url} -> ${res.status}`);
  return (await res.json()) as T;
}

async function fetchPapers(): Promise<PaperSummary[]> {
  const data = await getJson<{ papers: PaperSummary[] }>(PAPERS_URL);
  if (!Array.isArray(data.papers)) throw new Error("papers: expected an array");
  return data.papers;
}

async function fetchLedger(slug: string): Promise<Ledger> {
  const data = await getJson<Ledger>(`${PAPERS_URL}/${encodeURIComponent(slug)}`);
  if (!data?.paper) throw new Error("ledger: malformed");
  return data;
}

interface Loaded<T> {
  data: T;
  /** false until the live fetch resolves; true once we're showing backend (or mock) data. */
  live: boolean;
  loading: boolean;
}

/** The index spectrum: live papers, falling back to the real-data fixture offline. */
export function usePapers(): Loaded<PaperSummary[]> {
  const [data, setData] = React.useState<PaperSummary[]>(REPRO_PAPERS);
  const [live, setLive] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  React.useEffect(() => {
    let on = true;
    fetchPapers()
      .then((papers) => {
        if (!on) return;
        setData(papers);
        setLive(true);
      })
      .catch(() => {
        /* backend unreachable -> keep the embedded fixture */
      })
      .finally(() => on && setLoading(false));
    return () => {
      on = false;
    };
  }, []);
  return { data, live, loading };
}

/** One paper's full ledger: live, falling back to the fixture (or null if unknown). */
export function useLedger(slug: string): Loaded<Ledger | null> {
  const fallback = REPRO_LEDGERS[slug] ?? null;
  const [data, setData] = React.useState<Ledger | null>(fallback);
  const [live, setLive] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  React.useEffect(() => {
    let on = true;
    setData(REPRO_LEDGERS[slug] ?? null);
    setLive(false);
    setLoading(true);
    fetchLedger(slug)
      .then((ledger) => {
        if (!on) return;
        setData(ledger);
        setLive(true);
      })
      .catch(() => {
        /* offline -> embedded fixture (already set) */
      })
      .finally(() => on && setLoading(false));
    return () => {
      on = false;
    };
  }, [slug]);
  return { data, live, loading };
}
