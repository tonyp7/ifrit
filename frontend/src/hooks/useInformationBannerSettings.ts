import { useCallback, useEffect, useReducer } from "react";

import { ApiError } from "@/api/client";
import { getInformationBannerSettings, patchInformationBannerSettings } from "@/api/settings";
import type { SettingSaveResult } from "@/hooks/useSettingField";
import type { SettingsLoad } from "@/hooks/usePdfExportSettings";
import type { BannerColor, BannerIcon, InformationBannerSettings } from "@/types/settings";

/** The part of the group edited as a draft and saved together by one button. */
export interface BannerDraft {
  message: string;
  icon: BannerIcon;
  color: BannerColor;
}

export interface InformationBannerState {
  load: SettingsLoad;
  /** What the server last confirmed; null until the first load succeeds. */
  saved: InformationBannerSettings | null;
  /** What the message box, icon and color show; null until the first load succeeds. */
  draft: BannerDraft | null;
  /** True while a save is in flight; the controls stay locked until it finishes. */
  saving: boolean;
}

export const initialInformationBannerState: InformationBannerState = {
  load: "loading",
  saved: null,
  draft: null,
  saving: false,
};

export type InformationBannerAction =
  | { type: "load" }
  | { type: "loaded"; settings: InformationBannerSettings }
  | { type: "load-failed" }
  | { type: "edit"; change: Partial<BannerDraft> }
  | { type: "save-start" }
  /** A switch was saved: the draft is somebody's unsaved work and is left alone. */
  | { type: "switch-saved"; settings: InformationBannerSettings }
  /** The draft was saved: it becomes what the server kept (the message comes back trimmed). */
  | { type: "draft-saved"; settings: InformationBannerSettings }
  | { type: "save-failure" };

function draftOf({ message, icon, color }: InformationBannerSettings): BannerDraft {
  return { message, icon, color };
}

export function informationBannerReducer(
  state: InformationBannerState,
  action: InformationBannerAction,
): InformationBannerState {
  switch (action.type) {
    case "load":
      return initialInformationBannerState;
    case "loaded":
      return {
        ...state,
        load: "ready",
        saved: action.settings,
        draft: draftOf(action.settings),
      };
    case "load-failed":
      return { ...state, load: "failed" };
    case "edit":
      return state.draft ? { ...state, draft: { ...state.draft, ...action.change } } : state;
    case "save-start":
      return { ...state, saving: true };
    case "switch-saved":
      return { ...state, saved: action.settings, saving: false };
    case "draft-saved":
      return {
        ...state,
        saved: action.settings,
        draft: draftOf(action.settings),
        saving: false,
      };
    case "save-failure":
      // `saved` and the draft are untouched: a switch shows its last saved position again
      // and the typed text stays.
      return { ...state, saving: false };
  }
}

/** Whether the draft differs from what is stored, which is when Save changes is offered. */
export function isDirty(state: InformationBannerState): boolean {
  const { saved, draft } = state;
  if (saved === null || draft === null) return false;
  return (
    draft.message !== saved.message || draft.icon !== saved.icon || draft.color !== saved.color
  );
}

/** One of the two switches of the group. */
export type BannerSwitchKey = "show_on_login" | "show_site_wide";

/**
 * What a switch change sends, and which transition follows. Turning a switch on while the
 * draft differs from what is stored saves the draft with it, in one request that succeeds
 * or fails as a whole: the person has just seen it in the preview and turning the banner on
 * is what publishes it. Turning a switch off, or on with nothing unsaved, sends the switch
 * alone and leaves any unsaved draft where it is.
 */
export function planSwitchSave(
  state: InformationBannerState,
  key: BannerSwitchKey,
  checked: boolean,
): { body: Partial<InformationBannerSettings>; done: "switch-saved" | "draft-saved" } {
  if (checked && state.draft && isDirty(state)) {
    return { body: { [key]: true, ...state.draft }, done: "draft-saved" };
  }
  return { body: { [key]: checked }, done: "switch-saved" };
}

/**
 * Sends one save and reports it as state transitions. Resolves, never throws, so a caller
 * only has to decide what to tell the user.
 */
export async function runBannerSave(
  send: () => Promise<InformationBannerSettings>,
  done: "switch-saved" | "draft-saved",
  dispatch: (action: InformationBannerAction) => void,
): Promise<SettingSaveResult> {
  dispatch({ type: "save-start" });
  try {
    dispatch({ type: done, settings: await send() });
    return { ok: true };
  } catch (failure) {
    dispatch({ type: "save-failure" });
    if (failure instanceof ApiError && failure.status >= 400 && failure.status < 500) {
      return { ok: false, rejected: true, message: failure.message };
    }
    return { ok: false, rejected: false };
  }
}

/** State and actions of the Information Banner card. */
export function useInformationBannerSettings() {
  const [state, dispatch] = useReducer(
    informationBannerReducer,
    initialInformationBannerState,
  );

  // Re-runs when `load` goes back to "loading" (retry), not on every state change.
  const loading = state.load === "loading";
  useEffect(() => {
    if (!loading) return;
    let cancelled = false;
    getInformationBannerSettings()
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
  const edit = useCallback(
    (change: Partial<BannerDraft>) => dispatch({ type: "edit", change }),
    [],
  );

  /** A switch is saved at once; turning one on also carries an unsaved draft (see planSwitchSave). */
  const setSwitch = useCallback(
    (key: BannerSwitchKey, checked: boolean) => {
      const { body, done } = planSwitchSave(state, key, checked);
      return runBannerSave(() => patchInformationBannerSettings(body), done, dispatch);
    },
    [state],
  );

  /** Resolves to null when there is nothing to save. */
  const saveDraft = useCallback(async (): Promise<SettingSaveResult | null> => {
    if (!state.draft || !isDirty(state)) return null;
    const draft = state.draft;
    return runBannerSave(() => patchInformationBannerSettings(draft), "draft-saved", dispatch);
  }, [state]);

  return { state, retry, edit, setSwitch, saveDraft };
}
