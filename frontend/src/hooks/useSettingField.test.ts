import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import {
  initialSettingFieldState,
  runSettingSave,
  settingFieldReducer,
  type SettingFieldAction,
  type SettingFieldState,
} from "@/hooks/useSettingField";

function replay(
  actions: SettingFieldAction<number>[],
  from: SettingFieldState<number> = initialSettingFieldState<number>(),
) {
  return actions.reduce(settingFieldReducer<number>, from);
}

const ready = replay([{ type: "loaded", value: 28800 }]);

describe("settingFieldReducer", () => {
  it("starts loading with no value", () => {
    expect(initialSettingFieldState()).toEqual({
      load: "loading",
      saved: null,
      saving: false,
    });
  });

  it("holds the saved value once loaded", () => {
    expect(ready).toEqual({ load: "ready", saved: 28800, saving: false });
  });

  it("goes back to loading on retry after a failed load", () => {
    const failed = replay([{ type: "load-failed" }]);
    expect(failed.load).toBe("failed");
    expect(replay([{ type: "load" }], failed)).toEqual(initialSettingFieldState());
  });

  it("adopts the server's value on success", () => {
    const state = replay(
      [{ type: "save-start" }, { type: "save-success", value: 25200 }],
      ready,
    );
    expect(state).toEqual({ load: "ready", saved: 25200, saving: false });
  });

  it("keeps the last saved value on failure", () => {
    const saving = replay([{ type: "save-start" }], ready);
    expect(saving.saving).toBe(true);
    expect(replay([{ type: "save-failure" }], saving)).toEqual(ready);
  });
});

describe("runSettingSave", () => {
  it("reports success", async () => {
    const dispatch = vi.fn();
    const result = await runSettingSave(() => Promise.resolve(25200), dispatch);

    expect(result).toEqual({ ok: true });
    expect(dispatch.mock.calls.map(([a]) => a.type)).toEqual(["save-start", "save-success"]);
  });

  it("reports a rejection with the server's reason", async () => {
    const dispatch = vi.fn();
    const result = await runSettingSave(
      () => Promise.reject(new ApiError(422, "Input should be at most 86400")),
      dispatch,
    );

    expect(result).toEqual({
      ok: false,
      rejected: true,
      message: "Input should be at most 86400",
    });
    expect(dispatch.mock.calls.at(-1)?.[0]).toEqual({ type: "save-failure" });
  });

  it("reports a network or server failure separately", async () => {
    const dispatch = vi.fn();
    const network = await runSettingSave(
      () => Promise.reject(new TypeError("offline")),
      dispatch,
    );
    const server = await runSettingSave(
      () => Promise.reject(new ApiError(500, "boom")),
      dispatch,
    );

    expect(network).toEqual({ ok: false, rejected: false });
    expect(server).toEqual({ ok: false, rejected: false });
  });
});
