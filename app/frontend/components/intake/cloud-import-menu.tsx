"use client";

import * as React from "react";
import { AlertCircle, ChevronDown, Cloud, HardDrive, Link2, Loader2, Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/ui/cn";
import { CLOUD_PROVIDERS, OAUTH_PROVIDERS, type CloudProvider } from "@/lib/cloud/providers";
import { importFromCloud } from "@/lib/cloud/api";
import { connectProvider } from "@/lib/cloud/nango";
import type { Dataset } from "@/lib/projects/types";

/** lucide icon per provider id (kept out of the pure `lib/cloud/providers` registry). */
const PROVIDER_ICON: Record<string, typeof Cloud> = {
  url: Link2,
  google: HardDrive,
  onedrive: Cloud,
  dropbox: Package,
};

/**
 * "Import from cloud ▾" — the peer of the drop-zone for files that live off the machine.
 *
 * URL/S3 fully works: paste a link → the backend streams it into the same intake→parse pipeline a
 * dropped file uses, and the returned dataset is handed back via `onImported`. Google Drive / OneDrive
 * / Dropbox render a Connect button that is visibly present but no-ops with a "coming soon" note until
 * the owner wires their OAuth client IDs into Nango (`CLOUD_CONNECT_ENABLED`).
 */
export function CloudImportMenu({
  projectId,
  onImported,
}: {
  projectId: string;
  onImported: (dataset: Dataset) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [url, setUrl] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [connectNote, setConnectNote] = React.useState<string | null>(null);
  const ref = React.useRef<HTMLDivElement>(null);

  // Close on outside click / Escape while open.
  React.useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function submitUrl() {
    const ref_ = url.trim();
    if (!ref_ || busy) return;
    setBusy(true);
    setError(null);
    try {
      const dataset = await importFromCloud(projectId, { provider: "url", ref: ref_ });
      onImported(dataset);
      setUrl("");
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't import from that link.");
    } finally {
      setBusy(false);
    }
  }

  async function connect(provider: CloudProvider) {
    setConnectNote(null);
    try {
      // Reachable only for a provider whose `comingSoon` is false (the button is disabled
      // otherwise); the backend still gates on its own per-provider settings flag and returns a
      // clear error if that is off, which is what `connectNote` surfaces.
      await connectProvider(provider.providerConfigKey, `${projectId}:${provider.id}`);
    } catch (e) {
      setConnectNote(
        e instanceof Error ? e.message : `${provider.label} — coming soon. Connect your account.`,
      );
    }
  }

  const urlProvider = CLOUD_PROVIDERS.find((p) => p.id === "url")!;

  return (
    <div ref={ref} className="relative">
      <Button
        variant="secondary"
        size="sm"
        className="gap-1.5"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <Cloud className="size-4" />
        Import from cloud
        <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} />
      </Button>

      {open && (
        <div
          role="dialog"
          aria-label="Import from cloud"
          className="absolute left-0 z-50 mt-2 w-80 origin-top-left rounded-xl border border-border bg-popover p-3 text-popover-foreground shadow-2xl ring-1 ring-border motion-safe:animate-in motion-safe:fade-in-0 motion-safe:zoom-in-95"
        >
          {/* URL / S3 — the working path */}
          <div className="space-y-1.5">
            <label htmlFor="cloud-import-url" className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Link2 className="size-3.5" />
              URL / S3 link
            </label>
            <div className="flex gap-1.5">
              <Input
                id="cloud-import-url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void submitUrl();
                }}
                placeholder="https://… or s3://bucket/key"
                spellCheck={false}
                autoComplete="off"
                disabled={busy}
              />
              <Button size="sm" onClick={() => void submitUrl()} disabled={busy || !url.trim()}>
                {busy ? <Loader2 className="size-4 animate-spin" /> : "Import"}
              </Button>
            </div>
            <p className="text-[11px] leading-snug text-muted-foreground">
              Paste a direct download link or an S3 URI — Selom streams it in and parses it like a dropped file.
            </p>
            {error && (
              <p className="flex items-start gap-1.5 text-[11px] leading-snug text-destructive">
                <AlertCircle className="mt-px size-3.5 shrink-0" />
                <span>{error}</span>
              </p>
            )}
          </div>

          <div className="my-3 h-px bg-border" />

          {/* OAuth providers. A provider whose `comingSoon` is set cannot succeed — its Connect
              button is DISABLED and says so at the control, rather than looking live and failing
              after the click (milestone review 2026-07-25, findings B4/B9). The flag is still an FE
              literal that cannot track the backend's per-provider settings flags (finding A20) —
              closing that fork needs a providers endpoint the FE reads, which lands with the cloud
              import/export slice. */}
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Connect an account
          </p>
          <ul className="space-y-1">
            {OAUTH_PROVIDERS.map((p) => {
              const Icon = PROVIDER_ICON[p.id] ?? Cloud;
              return (
                <li
                  key={p.id}
                  className="flex items-center gap-2.5 rounded-lg border border-border/70 bg-background/40 px-2.5 py-1.5"
                >
                  <span aria-hidden className="grid size-7 place-items-center rounded-md border border-border bg-background/70 text-muted-foreground [&_svg]:size-4">
                    <Icon />
                  </span>
                  <span className="flex-1 text-sm text-foreground/85">{p.label}</span>
                  {p.comingSoon && (
                    <span className="rounded-full border border-border bg-muted/60 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                      Soon
                    </span>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2.5 text-xs"
                    disabled={p.comingSoon}
                    title={p.comingSoon ? `${p.label} import is not enabled yet` : undefined}
                    onClick={() => void connect(p)}
                  >
                    Connect
                  </Button>
                </li>
              );
            })}
          </ul>
          {connectNote && (
            <p className="mt-2 rounded-md border border-border/70 bg-muted/40 px-2.5 py-1.5 text-[11px] leading-snug text-muted-foreground">
              {connectNote}
            </p>
          )}
          {OAUTH_PROVIDERS.some((p) => p.comingSoon) && (
            <p className="mt-2 text-[11px] leading-snug text-muted-foreground">
              {urlProvider.label} import works now. Account connections arrive with cloud import.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
