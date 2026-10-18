import { useCallback, useEffect, useReducer } from "react";

import { ApiError } from "@/api/client";
import type { SettingsLoad } from "@/hooks/usePdfExportSettings";

export interface SettingFieldState<T> {
  load: SettingsLoad;
  /** What the server last confirmed; null until the first load succeeds. */
  saved: T | null;
  /** True while a save is in flight; the field stays locked until it finishes. */
  saving: boolean;
}

export type SettingFieldAction<T> =
  | { type: "load" }
  | { type: "loaded"; value: T }
  | { type: "load-failed" }
  | { type: "save-start" }
  | { type: "save-success"; value: T }
  | { type: "save-failure" };

export function initialSettingFieldState<T>(): SettingFieldState<T> {
  return { load: "loading", saved: null, saving: false };
}

export function settingFieldReducer<T>(
  state: SettingFieldState<T>,
  action: SettingFieldAction<T>,
): SettingFieldState<T> {
  switch (action.type) {
    case "load":
      return initialSettingFieldState<T>();
    case "loaded":
      return { ...state, load: "ready", saved: action.value };
    case "load-failed":
      return { ...state, load: "failed" };
    case "save-start":
      return { ...state, saving: true };
    case "save-success":
      // The server's answer is the source of truth, whatever was sent (a trimmed name).
      return { ...state, saved: action.value, saving: false };
    case "save-failure":
      // `saved` is untouched, so the field shows the last saved value again.
      return { ...state, saving: false };
  }
}

export type SettingSaveResult =
  | { ok: true }
  /** The server looked at the value and refused it (4xx), `message` is its reason. */
  | { ok: false; rejected: true; message: string }
  /** The request itself failed (network, 5xx): says nothing about the value. */
  | { ok: false; rejected: false };

/**
 * Saves one value and reports it as state transitions. Resolves, never throws, so a
 * caller only has to decide what to tell the user.
 */
export async function runSettingSave<T>(
  send: () => Promise<T>,
  dispatch: (action: SettingFieldAction<T>) => void,
): Promise<SettingSaveResult> {
  dispatch({ type: "save-start" });
  try {
    dispatch({ type: "save-success", value: await send() });
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
 * Load and save state of one scalar setting. `read` fetches the setting's current value
 * and `write` saves a new one and returns the value the server kept.
 */
export function useSettingField<T>(read: () => Promise<T>, write: (value: T) => Promise<T>) {
  const [state, dispatch] = useReducer(
    settingFieldReducer<T>,
    undefined,
    initialSettingFieldState<T>,
  );

  // Re-runs when `load` goes back to "loading" (retry), not on every state change.
  const loading = state.load === "loading";
  useEffect(() => {
    if (!loading) return;
    let cancelled = false;
    read()
      .then((value) => {
        if (!cancelled) dispatch({ type: "loaded", value });
      })
      .catch(() => {
        if (!cancelled) dispatch({ type: "load-failed" });
      });
    return () => {
      cancelled = true;
    };
  }, [loading, read]);

  const retry = useCallback(() => dispatch({ type: "load" }), []);

  /** Resolves to null when the value equals the saved one, so nothing was sent. */
  const commit = useCallback(
    async (value: T): Promise<SettingSaveResult | null> => {
      if (state.saved === null || state.saving || state.saved === value) return null;
      return runSettingSave(() => write(value), dispatch);
    },
    [state.saved, state.saving, write],
  );

  return { state, retry, commit };
}
