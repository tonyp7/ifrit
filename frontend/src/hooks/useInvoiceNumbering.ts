import { useCallback, useEffect, useReducer } from "react";

import { ApiError } from "@/api/client";
import { getNumbering, saveNumberingFormat, setNextNumber } from "@/api/invoiceNumbering";
import type { SettingsLoad } from "@/hooks/usePdfExportSettings";
import { editorReducer, initialEditorState, tokensFromItems } from "@/lib/invoiceNumbering";
import type { NumberingState } from "@/types/invoiceNumbering";

export interface NumberingLoadState {
  load: SettingsLoad;
  /** What the server last returned; null until the first load succeeds. */
  saved: NumberingState | null;
  /** Which request is in flight, if any; the card's actions stay locked meanwhile. */
  busy: "format" | "next" | null;
}

export type NumberingLoadAction =
  | { type: "load" }
  | { type: "loaded"; state: NumberingState }
  | { type: "load-failed" }
  | { type: "start"; request: "format" | "next" }
  | { type: "done"; state: NumberingState | null };

export const initialNumberingLoadState: NumberingLoadState = {
  load: "loading",
  saved: null,
  busy: null,
};

export function numberingLoadReducer(
  state: NumberingLoadState,
  action: NumberingLoadAction,
): NumberingLoadState {
  switch (action.type) {
    case "load":
      return initialNumberingLoadState;
    case "loaded":
      return { load: "ready", saved: action.state, busy: null };
    case "load-failed":
      return { ...state, load: "failed" };
    case "start":
      return { ...state, busy: action.request };
    case "done":
      // A failed request leaves the saved state as it was.
      return { ...state, saved: action.state ?? state.saved, busy: null };
  }
}

export type NumberingResult =
  | { ok: true }
  /** The server refused it (4xx); `status` tells a conflict from a rejection. */
  | { ok: false; rejected: true; status: number; message: string }
  /** The request itself failed (network, 5xx). */
  | { ok: false; rejected: false };

/** Runs one request and reports it as transitions. Resolves, never throws. */
export async function runNumberingRequest(
  request: "format" | "next",
  send: () => Promise<NumberingState>,
  dispatch: (action: NumberingLoadAction) => void,
): Promise<NumberingResult> {
  dispatch({ type: "start", request });
  try {
    dispatch({ type: "done", state: await send() });
    return { ok: true };
  } catch (failure) {
    dispatch({ type: "done", state: null });
    if (failure instanceof ApiError && failure.status >= 400 && failure.status < 500) {
      return { ok: false, rejected: true, status: failure.status, message: failure.message };
    }
    return { ok: false, rejected: false };
  }
}

/** Load and save state of the Invoice Numbering card, with the format editor's state. */
export function useInvoiceNumbering() {
  const [state, dispatch] = useReducer(numberingLoadReducer, initialNumberingLoadState);
  const [editor, dispatchEditor] = useReducer(editorReducer, [], initialEditorState);

  // Re-runs when `load` goes back to "loading" (retry), not on every state change.
  const loading = state.load === "loading";
  useEffect(() => {
    if (!loading) return;
    let cancelled = false;
    getNumbering()
      .then((loaded) => {
        if (cancelled) return;
        dispatch({ type: "loaded", state: loaded });
        dispatchEditor({ type: "load", tokens: loaded.tokens });
      })
      .catch(() => {
        if (!cancelled) dispatch({ type: "load-failed" });
      });
    return () => {
      cancelled = true;
    };
  }, [loading]);

  const retry = useCallback(() => dispatch({ type: "load" }), []);

  const saveFormat = useCallback(
    async (confirm: boolean) => {
      const tokens = tokensFromItems(editor.items);
      const result = await runNumberingRequest(
        "format",
        () => saveNumberingFormat(tokens, confirm),
        dispatch,
      );
      // The editor keeps the edits on failure; on success it starts again from what was
      // saved, with a fresh undo history.
      if (result.ok) dispatchEditor({ type: "load", tokens });
      return result;
    },
    [editor.items],
  );

  const saveNext = useCallback(
    (value: number) => runNumberingRequest("next", () => setNextNumber(value), dispatch),
    [],
  );

  return { state, editor, dispatchEditor, retry, saveFormat, saveNext };
}
