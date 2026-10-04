import { useCallback, useEffect, useReducer } from "react";

import { ApiError } from "@/api/client";
import { getPdfExportSettings, patchPdfExportSettings } from "@/api/settings";
import type { PdfExportSettings } from "@/types/settings";

export type SettingsLoad = "loading" | "ready" | "failed";

export interface PdfExportState {
  load: SettingsLoad;
  /** What the server last confirmed; null until the first load succeeds. */
  saved: PdfExportSettings | null;
  /** Slider position while the thumb moves; null when it simply shows the saved value. */
  draftHeight: number | null;
  /** True while a save is in flight; the controls stay locked until it finishes. */
  saving: boolean;
}

export const initialPdfExportState: PdfExportState = {
  load: "loading",
  saved: null,
  draftHeight: null,
  saving: false,
};

export type PdfExportAction =
  | { type: "load" }
  | { type: "loaded"; settings: PdfExportSettings }
  | { type: "load-failed" }
  | { type: "drag"; value: number }
  | { type: "drag-ended" }
  | { type: "save-start" }
  | { type: "save-success"; settings: PdfExportSettings }
  | { type: "save-failure" };

export function pdfExportReducer(
  state: PdfExportState,
  action: PdfExportAction,
): PdfExportState {
  switch (action.type) {
    case "load":
      return { ...initialPdfExportState };
    case "loaded":
      return { ...state, load: "ready", saved: action.settings };
    case "load-failed":
      return { ...state, load: "failed" };
    case "drag":
      // Only local state: moving the thumb never reaches the server by itself.
      return state.load === "ready" && !state.saving
        ? { ...state, draftHeight: action.value }
        : state;
    case "drag-ended":
      return { ...state, draftHeight: null };
    case "save-start":
      return { ...state, saving: true };
    case "save-success":
      // The server's answer is the source of truth, whatever was sent.
      return { ...state, saved: action.settings, draftHeight: null, saving: false };
    case "save-failure":
      // Back to the last saved value: the failed change is not shown as if it stuck.
      return { ...state, draftHeight: null, saving: false };
  }
}

/** The height the slider and its label show: the thumb's position while it moves. */
export function displayedHeight(state: PdfExportState): number | null {
  return state.draftHeight ?? state.saved?.logo_height_mm ?? null;
}

export type SaveResult =
  | { ok: true }
  /** The server looked at the value and refused it (4xx), `message` is its reason. */
  | { ok: false; rejected: true; message: string }
  /** The request itself failed (network, 5xx): says nothing about the value. */
  | { ok: false; rejected: false };

/**
 * Saves one change and reports it as state transitions. Resolves, never throws, so a
 * caller only has to decide what to tell the user.
 */
export async function runSave(
  send: () => Promise<PdfExportSettings>,
  dispatch: (action: PdfExportAction) => void,
): Promise<SaveResult> {
  dispatch({ type: "save-start" });
  try {
    dispatch({ type: "save-success", settings: await send() });
    return { ok: true };
  } catch (failure) {
    dispatch({ type: "save-failure" });
    if (failure instanceof ApiError && failure.status >= 400 && failure.status < 500) {
      return { ok: false, rejected: true, message: failure.message };
    }
    return { ok: false, rejected: false };
  }
}

/**
 * Whether committing `value` on the slider needs a request: releasing the thumb where
 * it started changes nothing, so it sends nothing.
 */
export function heightNeedsSave(state: PdfExportState, value: number): boolean {
  return state.saved !== null && state.saved.logo_height_mm !== value;
}

/** State and actions of the PDF Report Export card. */
export function usePdfExportSettings() {
  const [state, dispatch] = useReducer(pdfExportReducer, initialPdfExportState);

  // Re-runs when `load` goes back to "loading" (retry), not on every state change.
  const loading = state.load === "loading";
  useEffect(() => {
    if (!loading) return;
    let cancelled = false;
    getPdfExportSettings()
      .then((settings) => {
        if (!cancelled) dispatch({ type: "loaded", settings });
      })
      .catch(() => {
        if (!cancelled) dispatch({ type: "load-failed" });
      });
    return () => {
      cancelled = true;
    };
  }, [loading]);

  const retry = useCallback(() => dispatch({ type: "load" }), []);

  const setExportLogo = useCallback(
    (checked: boolean) =>
      runSave(() => patchPdfExportSettings({ export_logo: checked }), dispatch),
    [],
  );

  const dragHeight = useCallback((value: number) => dispatch({ type: "drag", value }), []);

  /** Resolves to null when nothing needed saving. */
  const commitHeight = useCallback(
    async (value: number): Promise<SaveResult | null> => {
      if (!heightNeedsSave(state, value)) {
        dispatch({ type: "drag-ended" });
        return null;
      }
      return runSave(() => patchPdfExportSettings({ logo_height_mm: value }), dispatch);
    },
    [state],
  );

  return { state, retry, setExportLogo, dragHeight, commitHeight };
}
