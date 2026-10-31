import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import {
  informationBannerReducer,
  initialInformationBannerState,
  isDirty,
  planSwitchSave,
  runBannerSave,
  type InformationBannerAction,
  type InformationBannerState,
} from "@/hooks/useInformationBannerSettings";
import type { InformationBannerSettings } from "@/types/settings";

const saved: InformationBannerSettings = {
  show_on_login: false,
  show_site_wide: false,
  message: "",
  icon: "info",
  color: "neutral",
};

function replay(
  actions: InformationBannerAction[],
  from: InformationBannerState = initialInformationBannerState,
) {
  return actions.reduce(informationBannerReducer, from);
}

const ready = replay([{ type: "loaded", settings: saved }]);

describe("informationBannerReducer", () => {
  it("starts loading with nothing known", () => {
    expect(initialInformationBannerState.load).toBe("loading");
    expect(initialInformationBannerState.draft).toBeNull();
  });

  it("fills the draft from the saved values once loaded, and is not dirty", () => {
    expect(ready.load).toBe("ready");
    expect(ready.draft).toEqual({ message: "", icon: "info", color: "neutral" });
    expect(isDirty(ready)).toBe(false);
  });

  it("goes back to loading on retry after a failed load", () => {
    const failed = replay([{ type: "load-failed" }]);
    expect(failed.load).toBe("failed");
    expect(replay([{ type: "load" }], failed)).toEqual(initialInformationBannerState);
  });

  it("is dirty as soon as the message, icon or color differs, and clean when it is put back", () => {
    const typed = replay([{ type: "edit", change: { message: "Hi" } }], ready);
    expect(isDirty(typed)).toBe(true);
    expect(isDirty(replay([{ type: "edit", change: { icon: "warning" } }], ready))).toBe(true);
    expect(isDirty(replay([{ type: "edit", change: { color: "red" } }], ready))).toBe(true);
    expect(isDirty(replay([{ type: "edit", change: { message: "" } }], typed))).toBe(false);
  });

  it("ignores edits before the first load", () => {
    expect(replay([{ type: "edit", change: { message: "x" } }])).toEqual(
      initialInformationBannerState,
    );
  });

  it("keeps an unsaved draft when a switch is saved", () => {
    const typed = replay([{ type: "edit", change: { message: "Unsaved" } }], ready);
    const after = replay(
      [
        { type: "save-start" },
        { type: "switch-saved", settings: { ...saved, show_on_login: true } },
      ],
      typed,
    );

    expect(after.saved?.show_on_login).toBe(true);
    expect(after.draft?.message).toBe("Unsaved");
    expect(after.saving).toBe(false);
    expect(isDirty(after)).toBe(true);
  });

  it("takes the server's answer into the draft when the draft is saved", () => {
    const typed = replay([{ type: "edit", change: { message: "  Hi  " } }], ready);
    const after = replay(
      [{ type: "draft-saved", settings: { ...saved, message: "Hi" } }],
      typed,
    );

    expect(after.draft?.message).toBe("Hi");
    expect(isDirty(after)).toBe(false);
  });

  it("keeps the draft and the saved values when a save fails", () => {
    const typed = replay([{ type: "edit", change: { message: "Keep me" } }], ready);
    const after = replay([{ type: "save-start" }, { type: "save-failure" }], typed);

    expect(after.saved).toEqual(saved);
    expect(after.draft?.message).toBe("Keep me");
    expect(after.saving).toBe(false);
  });
});

describe("runBannerSave", () => {
  it("dispatches the save and reports success", async () => {
    const dispatch = vi.fn();
    const result = await runBannerSave(() => Promise.resolve(saved), "draft-saved", dispatch);

    expect(result).toEqual({ ok: true });
    expect(dispatch).toHaveBeenNthCalledWith(1, { type: "save-start" });
    expect(dispatch).toHaveBeenNthCalledWith(2, { type: "draft-saved", settings: saved });
  });

  it("reports the server's reason for a rejection", async () => {
    const dispatch = vi.fn();
    const result = await runBannerSave(
      () => Promise.reject(new ApiError(422, "String should have at most 200 characters")),
      "draft-saved",
      dispatch,
    );

    expect(result).toEqual({
      ok: false,
      rejected: true,
      message: "String should have at most 200 characters",
    });
    expect(dispatch).toHaveBeenLastCalledWith({ type: "save-failure" });
  });

  it("reports a failure to reach the server separately from a rejection", async () => {
    const result = await runBannerSave(
      () => Promise.reject(new TypeError("Failed to fetch")),
      "switch-saved",
      vi.fn(),
    );

    expect(result).toEqual({ ok: false, rejected: false });
  });
});

describe("planSwitchSave", () => {
  const typed = replay(
    [{ type: "edit", change: { message: "  Maintenance  ", icon: "warning", color: "red" } }],
    ready,
  );

  it("sends the draft with the switch when turning a switch on with unsaved changes", () => {
    expect(planSwitchSave(typed, "show_on_login", true)).toEqual({
      body: { show_on_login: true, message: "  Maintenance  ", icon: "warning", color: "red" },
      done: "draft-saved",
    });
  });

  it("sends only the switch when turning it on with nothing unsaved", () => {
    expect(planSwitchSave(ready, "show_site_wide", true)).toEqual({
      body: { show_site_wide: true },
      done: "switch-saved",
    });
  });

  it("sends only the switch when turning it off, and leaves an unsaved draft alone", () => {
    expect(planSwitchSave(typed, "show_site_wide", false)).toEqual({
      body: { show_site_wide: false },
      done: "switch-saved",
    });
    const after = replay(
      [{ type: "switch-saved", settings: { ...saved, show_site_wide: false } }],
      typed,
    );
    expect(after.draft?.message).toBe("  Maintenance  ");
    expect(isDirty(after)).toBe(true);
  });

  it("sends only the switch before the first load", () => {
    expect(planSwitchSave(initialInformationBannerState, "show_on_login", true)).toEqual({
      body: { show_on_login: true },
      done: "switch-saved",
    });
  });

  it("ends with the draft equal to the saved values once the server accepts it", () => {
    const answer = {
      ...saved,
      show_on_login: true,
      message: "Maintenance",
      icon: "warning" as const,
      color: "red" as const,
    };
    const after = replay([{ type: "draft-saved", settings: answer }], typed);

    expect(after.saved).toEqual(answer);
    expect(after.draft).toEqual({ message: "Maintenance", icon: "warning", color: "red" });
    expect(isDirty(after)).toBe(false);
  });

  it("keeps the draft and the saved values when the switch-on is rejected or fails", async () => {
    for (const failure of [new ApiError(422, "Too long"), new TypeError("Failed to fetch")]) {
      const dispatch = vi.fn();
      const { done } = planSwitchSave(typed, "show_on_login", true);
      const result = await runBannerSave(() => Promise.reject(failure), done, dispatch);

      expect(result.ok).toBe(false);
      const after = [{ type: "save-start" }, { type: "save-failure" }].reduce(
        (state, action) => informationBannerReducer(state, action as InformationBannerAction),
        typed,
      );
      expect(after.saved).toEqual(saved);
      expect(after.draft).toEqual(typed.draft);
    }
  });
});
