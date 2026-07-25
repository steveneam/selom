"use client";

import * as React from "react";
import { AlertCircle, ChevronDown, Cloud, HardDrive, Link2, Loader2, Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/ui/cn";
import { FALLBACK_CLOUD_PROVIDERS, type CloudProvider } from "@/lib/cloud/providers";
import {
  fetchCloudConnections,
  fetchCloudProviders,
  importFromCloud,
  type CloudConnection,
} from "@/lib/cloud/api";
import type { Dataset } from "@/lib/projects/types";

/** lucide icon per provider id (kept out of the pure `lib/cloud/providers` registry). */
const PROVIDER_ICON: Record<string, typeof Cloud> = {
  url: Link2,
  google: HardDrive,
  onedrive: Cloud,
  dropbox: Package,
};

/** What to type into an OAuth provider's reference box, per provider. */
const REF_HINT: Record<string, { placeholder: string; help: string }> = {
  google: {
    placeholder: "Drive file id (from the share link)",
    help: "Open the file in Drive → Share → Copy link; the id is the /d/<id>/ segment.",
  },
  dropbox: {
    placeholder: "/folder/file.h5ad",
    help: "The file's path inside your Dropbox, including the leading slash.",
  },
  onedrive: { placeholder: "item id", help: "The OneDrive item id." },
};

/**
 * "Import from cloud ▾" — the peer of the drop-zone for files that live off the machine.
 *
 * **The server owns provider state.** The menu is rendered from `GET /cloud/providers` (the frozen
 * contract, `lib/cloud/contract.ts`) in the order received, and every disabled affordance derives
 * from that response's `enabled`. This component used to read a local table with a hardcoded
 * `comingSoon: true`, so both live OAuth providers stayed unreachable in the UI (A20) — hence the
 * rule: no client-side provider truth, ever.
 *
 * Three honest states per OAuth provider, instead of one button that lies:
 * - not enabled → "Not enabled" chip, no import form;
 * - enabled, no account connected → says so, and names what is missing (L2-07, the Connect UI host);
 * - enabled + connected → the account label and a reference box that really imports.
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
  const [busy, setBusy] = React.useState<string | null>(null); // the provider id being imported
  const [error, setError] = React.useState<string | null>(null);
  const [providers, setProviders] = React.useState<CloudProvider[] | null>(null);
  // The provider list is the OFFLINE fallback, not the server's answer — the menu must say so.
  const [degraded, setDegraded] = React.useState(false);
  const [connections, setConnections] = React.useState<CloudConnection[] | null>(null);
  const [connectionsError, setConnectionsError] = React.useState<string | null>(null);
  const ref = React.useRef<HTMLDivElement>(null);

  // Load the server's menu the first time it's opened (not on mount — this sits on the Data tab of
  // every project and the list is only needed once the popover is actually shown).
  // The guard is a REF, not `providers`, and `providers` is not a dependency. It used to be both,
  // which made this effect cancel itself halfway: `setProviders(list)` changed the dep, React ran
  // the cleanup (`live = false`), and the connections request — still in flight one line below —
  // landed with every setter gated off. `connections` stayed `null` forever, so every OAuth
  // provider rendered with no "Connected" chip, no import form, and no error to explain why.
  // Deterministic, not a race: the providers fetch always resolves first. It made the whole OAuth
  // cloud-import path unreachable in the UI while every backend gate stayed green
  // (V-2, browser-verified 2026-07-25).
  const loadedRef = React.useRef(false);
  React.useEffect(() => {
    if (!open || loadedRef.current) return;
    loadedRef.current = true;
    let live = true;
    void (async () => {
      let ok = true;
      try {
        const list = await fetchCloudProviders();
        if (!live) return;
        setProviders(list);
        setDegraded(false);
      } catch {
        if (!live) return;
        setProviders(FALLBACK_CLOUD_PROVIDERS);
        setDegraded(true);
        ok = false;
      }
      try {
        const conns = await fetchCloudConnections();
        if (live) {
          setConnections(conns);
          setConnectionsError(null);
        }
      } catch (e) {
        // Only the account section degrades — URL/S3 needs no broker and keeps working.
        if (live) {
          setConnections([]);
          setConnectionsError(
            e instanceof Error ? e.message : "Couldn't check which accounts are connected.",
          );
          ok = false;
        }
      }
      // A load that failed — or was abandoned because the menu closed mid-flight — must be
      // retryable, or the degraded banner's "Reopen this menu once you're back online" is a lie
      // and a menu closed while loading stays on "Loading import options…" forever.
      if (!ok || !live) loadedRef.current = false;
    })();
    return () => {
      live = false;
    };
  }, [open]);

  // Keep the popover inside the viewport. It opens BELOW a trigger that already sits well down the
  // Data stage, so at 1280×800 with both accounts connected it ran 40px past the fold and the part
  // that got cut was the bottom row — a provider's import form (measured, D-8). The menu grew into
  // that when the connected state started rendering at all, which is exactly the sort of thing a
  // fixed max-height would have missed: the constraint is the space BELOW the trigger, not a
  // constant. Clamp to what is actually there and scroll inside.
  const [maxH, setMaxH] = React.useState<number | null>(null);
  React.useEffect(() => {
    if (!open) return;
    const measure = () => {
      const el = ref.current;
      if (!el) return;
      const bottom = el.getBoundingClientRect().bottom;
      // 8px for the trigger gap (mt-2), 12px of breathing room at the viewport edge.
      setMaxH(Math.max(200, Math.round(window.innerHeight - bottom - 20)));
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [open]);

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

  /** One import, whichever provider it came from. `close` collapses the menu on success. */
  async function submit(provider: string, ref_: string, connectionId?: string) {
    const trimmed = ref_.trim();
    if (!trimmed || busy) return false;
    setBusy(provider);
    setError(null);
    try {
      const dataset = await importFromCloud(projectId, {
        provider,
        ref: trimmed,
        connectionId,
      });
      onImported(dataset);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't import that file.");
      return false;
    } finally {
      setBusy(null);
    }
  }

  const list = providers ?? [];
  const urlProvider = list.find((p) => p.kind === "url");
  const oauthProviders = list.filter((p) => p.kind === "oauth");
  const connectionFor = (id: string) => connections?.find((c) => c.provider === id);

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
          style={maxH ? { maxHeight: maxH } : undefined}
          className="absolute left-0 z-50 mt-2 w-96 origin-top-left overflow-y-auto rounded-xl border border-border bg-popover p-3 text-popover-foreground shadow-2xl ring-1 ring-border motion-safe:animate-in motion-safe:fade-in-0 motion-safe:zoom-in-95"
        >
          {!providers ? (
            <p className="flex items-center gap-2 py-2 text-xs text-muted-foreground" role="status">
              <Loader2 className="size-3.5 animate-spin" />
              Loading import options…
            </p>
          ) : (
            <>
              {/* URL / S3 — needs no account, so it is always the first thing offered. */}
              {urlProvider && (
                <div className="space-y-1.5">
                  <label
                    htmlFor="cloud-import-url"
                    className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    <Link2 className="size-3.5" />
                    {urlProvider.label}
                  </label>
                  <div className="flex gap-1.5">
                    <Input
                      id="cloud-import-url"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          void submit("url", url).then((ok) => {
                            if (ok) {
                              setUrl("");
                              setOpen(false);
                            }
                          });
                        }
                      }}
                      placeholder="https://… or s3://bucket/key"
                      spellCheck={false}
                      autoComplete="off"
                      disabled={busy !== null}
                    />
                    <ImportButton
                      busy={busy === "url"}
                      disabled={busy !== null || !url.trim()}
                      label="Import from a URL or S3 link"
                      onClick={() =>
                        void submit("url", url).then((ok) => {
                          if (ok) {
                            setUrl("");
                            setOpen(false);
                          }
                        })
                      }
                    />
                  </div>
                  <p className="text-[11px] leading-snug text-muted-foreground">
                    Paste a direct download link or an S3 URI — Selom streams it in and parses it like a dropped file.
                  </p>
                </div>
              )}

              {error && (
                <p className="mt-1.5 flex items-start gap-1.5 text-[11px] leading-snug text-destructive" role="alert">
                  <AlertCircle className="mt-px size-3.5 shrink-0" />
                  <span>{error}</span>
                </p>
              )}

              <div className="my-3 h-px bg-border" />

              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Your connected accounts
              </p>
              <ul className="space-y-1.5">
                {oauthProviders.map((p) => (
                  <ProviderRow
                    key={p.id}
                    provider={p}
                    connection={connectionFor(p.id)}
                    connectionsKnown={connections !== null}
                    busy={busy === p.id}
                    anyBusy={busy !== null}
                    onImport={(ref_, connectionId) =>
                      submit(p.id, ref_, connectionId).then((ok) => {
                        if (ok) setOpen(false);
                        return ok;
                      })
                    }
                  />
                ))}
              </ul>

              {connectionsError && (
                <p className="mt-2 rounded-md border border-warn/40 bg-warn/10 px-2.5 py-1.5 text-[11px] leading-snug text-warn">
                  Couldn&apos;t check your connected accounts ({connectionsError}). URL / S3 import still works.
                </p>
              )}
              {degraded && (
                <p className="mt-2 rounded-md border border-warn/40 bg-warn/10 px-2.5 py-1.5 text-[11px] leading-snug text-warn">
                  Showing the offline list — Selom couldn&apos;t reach the server, so it can&apos;t tell which
                  providers are enabled. Reopen this menu once you&apos;re back online.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * The Import control. The busy state is LABELLED — an unlabelled spinner tells a screen reader
 * nothing and tells a sighted user only that something is happening, not what (finding B22). The
 * accessible name stays stable while the visible text changes, and `aria-busy` marks the wait.
 */
function ImportButton({
  busy,
  disabled,
  label,
  onClick,
}: {
  busy: boolean;
  disabled: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <Button
      size="sm"
      className="shrink-0 gap-1.5"
      onClick={onClick}
      disabled={disabled}
      aria-busy={busy}
      aria-label={busy ? `${label} — importing…` : label}
    >
      {busy ? (
        <>
          <Loader2 className="size-3.5 animate-spin" />
          Importing…
        </>
      ) : (
        "Import"
      )}
    </Button>
  );
}

/**
 * One OAuth provider row. Which of the three states it renders is entirely the server's answer:
 * `enabled` from the frozen providers contract, `connection` from `/cloud/connections`. Nothing
 * here guesses.
 */
function ProviderRow({
  provider,
  connection,
  connectionsKnown,
  busy,
  anyBusy,
  onImport,
}: {
  provider: CloudProvider;
  connection: CloudConnection | undefined;
  /** False while the connections request is still in flight — don't claim "not connected" yet. */
  connectionsKnown: boolean;
  busy: boolean;
  anyBusy: boolean;
  onImport: (ref: string, connectionId?: string) => Promise<boolean>;
}) {
  const [ref, setRef] = React.useState("");
  const Icon = PROVIDER_ICON[provider.id] ?? Cloud;
  const hint = REF_HINT[provider.id];
  const inputId = `cloud-import-ref-${provider.id}`;

  return (
    <li className="rounded-lg border border-border/70 bg-background/40 px-2.5 py-2">
      <div className="flex items-center gap-2.5">
        <span
          aria-hidden
          className="grid size-7 shrink-0 place-items-center rounded-md border border-border bg-background/70 text-muted-foreground [&_svg]:size-4"
        >
          <Icon />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm text-foreground/85">{provider.label}</p>
          {connection && (
            <p className="truncate text-[11px] text-muted-foreground">{connection.label}</p>
          )}
        </div>
        {!provider.enabled ? (
          <span className="rounded-full border border-border bg-muted/60 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Not enabled
          </span>
        ) : connection ? (
          <span className="rounded-full border border-stage-publish/40 bg-[color-mix(in_oklab,var(--stage-publish)_12%,transparent)] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-stage-publish">
            Connected
          </span>
        ) : connectionsKnown ? (
          <span className="rounded-full border border-border bg-muted/60 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            No account
          </span>
        ) : null}
      </div>

      {/* Enabled + connected → the only state where an import can actually succeed. */}
      {provider.enabled && connection && (
        <div className="mt-2 space-y-1">
          <label htmlFor={inputId} className="sr-only">
            {provider.label} file reference
          </label>
          <div className="flex gap-1.5">
            <Input
              id={inputId}
              value={ref}
              onChange={(e) => setRef(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void onImport(ref, connection.connectionId);
              }}
              placeholder={hint?.placeholder ?? "file id"}
              spellCheck={false}
              autoComplete="off"
              disabled={anyBusy}
            />
            <ImportButton
              busy={busy}
              disabled={anyBusy || !ref.trim()}
              label={`Import from ${provider.label}`}
              onClick={() => void onImport(ref, connection.connectionId)}
            />
          </div>
          {hint && <p className="text-[11px] leading-snug text-muted-foreground">{hint.help}</p>}
        </div>
      )}

      {/* Enabled but nothing connected — say what is missing instead of offering a dead button. */}
      {provider.enabled && !connection && connectionsKnown && (
        <p className="mt-1.5 text-[11px] leading-snug text-muted-foreground">
          Enabled, but no {provider.label} account is connected yet. Connecting one from here needs the
          Nango Connect UI host (tracked as L2-07).
        </p>
      )}
    </li>
  );
}
