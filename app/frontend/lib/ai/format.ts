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

/**
 * The APPLIED (committed) ✨ marker's provenance tooltip — "AI · model · Jun 29, 14:32 · approved by
 * <id>". #12 surfaces `approved_by`, the server-trusted approver the chokepoint stamps at /ai/apply
 * (the audit trail the marker otherwise never showed). Empty fields are omitted, never printed blank.
 */
export function appliedMarkerTip(
  action?: Pick<AiAction, "actor" | "model" | "approved_at" | "approved_by">,
): string {
  if (!action) return "Applied by AI";
  const parts = [action.actor || "ai"];
  if (action.model) parts.push(action.model);
  const when = formatApprovedAt(action.approved_at);
  if (when) parts.push(when);
  if (action.approved_by) parts.push(`approved by ${action.approved_by}`);
  return parts.join(" · ");
}

/**
 * The STAGED (pre-commit) ✨ marker tooltip — "Staged by AI · proposed by <model>". #13: the model
 * shown is the PROPOSING gateway; with the delta refactor the FE no longer sends model to /ai/apply,
 * so the apply-time model can differ. Labelling it "proposed by" keeps the staged preview from
 * claiming it is the committed model (the documented propose→apply drift).
 */
export function stagedMarkerTip(model?: string): string {
  return `Staged by AI${model ? ` · proposed by ${model}` : ""}`;
}

/** The PROPOSED (un-acted) ✨ marker tooltip — "Proposed by AI · <model>". */
export function proposedMarkerTip(model?: string): string {
  return `Proposed by AI${model ? ` · ${model}` : ""}`;
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
