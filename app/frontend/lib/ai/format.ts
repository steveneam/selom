/**
 * Pure presentational helpers for the AI surfaces (S5) — kept in `lib/` (the repo's test home)
 * so they're unit-tested in the node env, separate from the presentational components that use
 * them (the ✨ marker, the activity feed, the banner proposal rows).
 */

import type { AiAction } from "./types";

/** Format an ISO timestamp to a short, locale-aware label; tolerant of an empty/invalid value. */
export function formatApprovedAt(iso?: string): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  return new Date(t).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Plain-language verb for an action type — the human-readable left side of a feed/banner row. */
export function describeAction(a: Pick<AiAction, "type">): string {
  switch (a.type) {
    case "set_param":
      return "Set parameter";
    case "add_filter":
      return "Added filter";
    case "remove_filter":
      return "Removed filter";
    case "restyle_figure":
      return "Restyled figure";
    case "relabel":
      return "Relabelled";
    case "set_profile":
      return "Set data type";
    case "set_design":
      return "Set design";
    case "map_columns":
      return "Mapped columns";
    case "apply_cleaning_step":
      return "Applied cleaning step";
    case "select_skill":
      return "Selected skill";
    default:
      return "Changed";
  }
}
