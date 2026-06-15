"use client";

import * as React from "react";
import { AlertCircle, Loader2, Palette } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { applyStyle, fetchStyles, type FigureStyle } from "@/lib/styles-api";
import { stampStyle } from "@/lib/figure-spec";
import type { Operation } from "@/lib/patch";
import type { FigureStore } from "@/hooks/use-figure-store";

/**
 * Journal-style picker for the editor toolbar (journal-styles v1).
 *
 * Picking a style restyles the live figure: the single Python theme transform runs
 * server-side and the result is committed as ONE undoable edit (replace data+layout),
 * so the figure stays editable and undo reverts the restyle. The active style is
 * STAMPED into the spec (layout.meta.selomStyle) as part of that same commit, so the
 * picker `value` is derived from the spec by the parent — undo rewinds the figure AND
 * the picker label together. Export is WYSIWYG, so the download reflects what's showing.
 * On failure nothing commits, so the controlled value stays put.
 */
export function StylePicker({
  store,
  skillId,
  value,
}: {
  store: FigureStore;
  skillId?: string;
  value: string;
}) {
  const [styles, setStyles] = React.useState<FigureStyle[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    fetchStyles()
      .then((s) => !cancelled && setStyles(s))
      .catch(() => {
        /* styles optional; the picker just stays on the current value */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function pick(styleId: string) {
    if (styleId === value || !store.spec) return;
    setBusy(true);
    setError(null);
    try {
      const styled = await applyStyle(store.spec, skillId, styleId);
      const label = styles.find((s) => s.id === styleId)?.label ?? styleId;
      const ops: Operation[] = [
        { op: "replace", path: "/data", value: styled.data },
        // Stamp the chosen style into the styled layout so undo rewinds the picker label.
        { op: "replace", path: "/layout", value: stampStyle(styled.layout, { id: styleId, label }) },
      ];
      store.commit(ops); // one undoable history entry (figure + style stamp together)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Style failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-1.5">
      <Palette className="size-3.5 text-muted-foreground" aria-hidden />
      <Select value={value} onValueChange={pick} disabled={busy || !store.spec}>
        <SelectTrigger className="h-8 w-[152px]" aria-label="Figure style">
          {busy ? (
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" /> Styling…
            </span>
          ) : (
            <SelectValue placeholder="Style" />
          )}
        </SelectTrigger>
        <SelectContent>
          {styles.map((s) => (
            <SelectItem key={s.id} value={s.id}>
              {s.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error && (
        <span title={error}>
          <AlertCircle className="size-4 text-destructive" aria-label={error} />
        </span>
      )}
    </div>
  );
}
