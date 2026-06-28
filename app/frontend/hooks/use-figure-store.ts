"use client";

import { useCallback, useMemo, useReducer } from "react";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import { normalizeSpec } from "@/lib/figure/figure-spec";
import { validateFigureContract } from "@/lib/figure/contract";
import { applyPatches, type Operation } from "@/lib/figure/patch";

/**
 * Holds the figure spec (source of truth) plus undo/redo.
 *
 * Checkpoint model: a live edit gesture (e.g. dragging a slider) calls `set` many
 * times but records ONE history entry. The first `set` stashes the pre-gesture
 * spec as `checkpoint`; `flush` (on release) pushes it onto the past. `commit` is
 * set+flush for discrete edits (selects, switches, colour, text). Because patches
 * apply immutably, the previous spec object is safe to keep as the checkpoint with
 * no cloning.
 */
interface State {
  present: FigureSpec | null;
  past: FigureSpec[];
  future: FigureSpec[];
  checkpoint: FigureSpec | null;
}

type Action =
  | { type: "init"; spec: FigureSpec }
  | { type: "set"; ops: Operation[] }
  | { type: "commit"; ops: Operation[] }
  | { type: "flush" }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "reset" };

const HISTORY_LIMIT = 60;
const cap = (stack: FigureSpec[]) =>
  stack.length > HISTORY_LIMIT ? stack.slice(stack.length - HISTORY_LIMIT) : stack;

const EMPTY: State = { present: null, past: [], future: [], checkpoint: null };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "init": {
      // Validate the spec shape at the data→component boundary (Task B2): an unknown / partial /
      // corrupt spec is coerced to a render-safe shape so init NEVER throws — it routes to a blank
      // (empty) figure instead of taking the editor down. A genuine figure passes through unchanged.
      const { spec } = validateFigureContract(action.spec);
      return { present: normalizeSpec(spec), past: [], future: [], checkpoint: null };
    }

    case "set": {
      if (!state.present || action.ops.length === 0) return state;
      const before = state.present; // immutable — safe to reuse as checkpoint
      return {
        ...state,
        present: applyPatches(before, action.ops),
        checkpoint: state.checkpoint ?? before,
      };
    }

    case "commit": {
      if (!state.present || action.ops.length === 0) return state;
      const before = state.present;
      const checkpoint = state.checkpoint ?? before;
      return {
        present: applyPatches(before, action.ops),
        past: cap([...state.past, checkpoint]),
        future: [],
        checkpoint: null,
      };
    }

    case "flush": {
      if (!state.checkpoint) return state;
      return {
        ...state,
        past: cap([...state.past, state.checkpoint]),
        future: [],
        checkpoint: null,
      };
    }

    case "undo": {
      if (state.past.length === 0 || !state.present) return state;
      const prev = state.past[state.past.length - 1];
      return {
        present: prev,
        past: state.past.slice(0, -1),
        future: [state.present, ...state.future],
        checkpoint: null,
      };
    }

    case "redo": {
      if (state.future.length === 0 || !state.present) return state;
      const next = state.future[0];
      return {
        present: next,
        past: [...state.past, state.present],
        future: state.future.slice(1),
        checkpoint: null,
      };
    }

    case "reset":
      return EMPTY;

    default:
      return state;
  }
}

export interface FigureStore {
  spec: FigureSpec | null;
  canUndo: boolean;
  canRedo: boolean;
  /** Load a fresh figure from a skill run (resets history). */
  init: (spec: FigureSpec) => void;
  /** Live preview during a gesture (no new history entry until flush). */
  set: (ops: Operation[]) => void;
  /** One atomic edit → one history entry. */
  commit: (ops: Operation[]) => void;
  /** End a live gesture, recording one history entry. */
  flush: () => void;
  undo: () => void;
  redo: () => void;
  reset: () => void;
}

export function useFigureStore(): FigureStore {
  const [state, dispatch] = useReducer(reducer, EMPTY);

  const init = useCallback((spec: FigureSpec) => dispatch({ type: "init", spec }), []);
  const set = useCallback((ops: Operation[]) => dispatch({ type: "set", ops }), []);
  const commit = useCallback((ops: Operation[]) => dispatch({ type: "commit", ops }), []);
  const flush = useCallback(() => dispatch({ type: "flush" }), []);
  const undo = useCallback(() => dispatch({ type: "undo" }), []);
  const redo = useCallback(() => dispatch({ type: "redo" }), []);
  const reset = useCallback(() => dispatch({ type: "reset" }), []);

  return useMemo(
    () => ({
      spec: state.present,
      canUndo: state.past.length > 0,
      canRedo: state.future.length > 0,
      init,
      set,
      commit,
      flush,
      undo,
      redo,
      reset,
    }),
    [state.present, state.past.length, state.future.length, init, set, commit, flush, undo, redo, reset],
  );
}
