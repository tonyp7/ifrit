import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import {
  displayedHeight,
  heightNeedsSave,
  initialPdfExportState,
  pdfExportReducer,
  runSave,
  type PdfExportAction,
  type PdfExportState,
} from "@/hooks/usePdfExportSettings";
import type { PdfExportSettings } from "@/types/settings";

const saved: PdfExportSettings = { export_logo: true, logo_height_mm: 20 };

function replay(actions: PdfExportAction[], from: PdfExportState = initialPdfExportState) {
  return actions.reduce(pdfExportReducer, from);
}

const ready = replay([{ type: "loaded", settings: saved }]);

describe("pdfExportReducer", () => {
  it("starts loading with nothing shown", () => {
    expect(initialPdfExportState.load).toBe("loading");
    expect(displayedHeight(initialPdfExportState)).toBeNull();
  });

  it("shows the saved value once loaded", () => {
    expect(ready.load).toBe("ready");
    expect(displayedHeight(ready)).toBe(20);
  });

  it("goes back to loading on retry after a failed load", () => {
    const failed = replay([{ type: "load-failed" }]);
    expect(failed.load).toBe("failed");
    expect(replay([{ type: "load" }], failed)).toEqual(initialPdfExportState);
  });

  it("follows the thumb while it moves, without saving anything", () => {
    const state = replay(
      [
        { type: "drag", value: 25 },
        { type: "drag", value: 30 },
      ],
      ready,
    );

    expect(displayedHeight(state)).toBe(30);
    expect(state.saved).toEqual(saved);
    expect(state.saving).toBe(false);
  });

  it("ignores the thumb before the settings are loaded and during a save", () => {
    expect(replay([{ type: "drag", value: 25 }])).toEqual(initialPdfExportState);

    const saving = replay([{ type: "save-start" }], ready);
    expect(replay([{ type: "drag", value: 25 }], saving)).toEqual(saving);
  });

  it("takes the server's answer as the new saved state after a save", () => {
    const state = replay(
      [
        { type: "drag", value: 30 },
        { type: "save-start" },
        { type: "save-success", settings: { export_logo: true, logo_height_mm: 30 } },
      ],
      ready,
    );

    expect(state.saved).toEqual({ export_logo: true, logo_height_mm: 30 });
    expect(displayedHeight(state)).toBe(30);
    expect(state.draftHeight).toBeNull();
    expect(state.saving).toBe(false);
  });

  it("returns to the last saved value when a save fails", () => {
    const state = replay(
      [{ type: "drag", value: 55 }, { type: "save-start" }, { type: "save-failure" }],
      ready,
    );

    expect(displayedHeight(state)).toBe(20);
    expect(state.saving).toBe(false);
  });

  it("locks the controls for the duration of a save", () => {
    expect(replay([{ type: "save-start" }], ready).saving).toBe(true);
  });
});

describe("heightNeedsSave", () => {
  it("is false for the value already saved", () => {
    expect(heightNeedsSave(ready, 20)).toBe(false);
  });

  it("is true for a different value", () => {
    expect(heightNeedsSave(ready, 21)).toBe(true);
  });

  it("is false before the settings are known", () => {
    expect(heightNeedsSave(initialPdfExportState, 21)).toBe(false);
  });
});

describe("runSave", () => {
  it("goes start -> success and returns ok", async () => {
    const dispatch = vi.fn();
    const answer = { export_logo: false, logo_height_mm: 20 };

    const result = await runSave(async () => answer, dispatch);

    expect(result).toEqual({ ok: true });
    expect(dispatch.mock.calls.map(([action]) => action)).toEqual([
      { type: "save-start" },
      { type: "save-success", settings: answer },
    ]);
  });

  it("reports a rejection with the server's reason, and reverts", async () => {
    const dispatch = vi.fn();

    const result = await runSave(async () => {
      throw new ApiError(422, "Input should be less than or equal to 60");
    }, dispatch);

    expect(result).toEqual({
      ok: false,
      rejected: true,
      message: "Input should be less than or equal to 60",
    });
    expect(dispatch).toHaveBeenLastCalledWith({ type: "save-failure" });
  });

  it("reports a server error as a failed request, not a rejection", async () => {
    const result = await runSave(async () => {
      throw new ApiError(500, "boom");
    }, vi.fn());

    expect(result).toEqual({ ok: false, rejected: false });
  });

  it("reports a dropped connection as a failed request, not a rejection", async () => {
    const dispatch = vi.fn();

    const result = await runSave(async () => {
      throw new TypeError("Failed to fetch");
    }, dispatch);

    expect(result).toEqual({ ok: false, rejected: false });
    expect(dispatch).toHaveBeenLastCalledWith({ type: "save-failure" });
  });
});
