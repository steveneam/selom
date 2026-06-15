"use client";

import * as React from "react";
import { AlertCircle, Loader2, Palette } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { applyStyle, fetchStyles, type FigureStyle } from "@/lib/styles-api";
import type { Operation } from "@/lib/patch";
import type { FigureStore } from "@/hooks/use-figure-store";

/**
 * Journal-style picker for the editor toolbar (journal-styles v1).
 *
 * Picking a style restyles the live figure: the single Python theme transform runs
 * server-side and the result is committed as ONE undoable edit (replace data+layout),
 * so the figure stays editable and undo reverts the restyle. Export is WYSIWYG, so the
 * download reflects whatever style is showing. On failure the controlled value reverts.
 */
export function StylePicker({
  store,
  skillId,
  value,
  onChange,
}: {
  store: FigureStore;
  skillId?: string;
  value: string;
  onChange: (id: string, label: string) => void;
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
      const ops: Operation[] = [
        { op: "replace", path: "/data", value: styled.data },
        { op: "replace", path: "/layout", value: styled.layout },
      ];
      store.commit(ops); // one undoable history entry
      onChange(styleId, styles.find((s) => s.id === styleId)?.label ?? styleId);
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
