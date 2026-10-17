import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import {
  initialNumberingLoadState,
  numberingLoadReducer,
  runNumberingRequest,
} from "@/hooks/useInvoiceNumbering";
import type { NumberingState } from "@/types/invoiceNumbering";

const saved: NumberingState = {
  tokens: [{ type: "sequence", digits: 4, start_at: 1, restart: "never" }],
  next_value: 1,
  preview: ["0001", "0002", "0003"],
  has_issued: false,
};

describe("numberingLoadReducer", () => {
  it("loads, retries and locks while a request runs", () => {
    const ready = numberingLoadReducer(initialNumberingLoadState, { type: "loaded", state: saved });
    expect(ready).toEqual({ load: "ready", saved, busy: null });
    const busy = numberingLoadReducer(ready, { type: "start", request: "next" });
    expect(busy.busy).toBe("next");
    expect(numberingLoadReducer(busy, { type: "done", state: null })).toEqual(ready);
    expect(numberingLoadReducer({ ...ready, load: "failed" }, { type: "load" })).toEqual(initialNumberingLoadState);
  });
});

describe("runNumberingRequest", () => {
  it("adopts the server's state on success", async () => {
    const dispatch = vi.fn();
    const next = { ...saved, next_value: 512 };
    expect(await runNumberingRequest("next", () => Promise.resolve(next), dispatch)).toEqual({ ok: true });
    expect(dispatch.mock.calls.at(-1)?.[0]).toEqual({ type: "done", state: next });
  });

  it("reports a conflict with its status and message", async () => {
    const result = await runNumberingRequest(
      "next",
      () => Promise.reject(new ApiError(409, "The number INV-2026-0007 already exists")),
      vi.fn(),
    );
    expect(result).toEqual({
      ok: false,
      rejected: true,
      status: 409,
      message: "The number INV-2026-0007 already exists",
    });
  });

  it("reports a network failure separately", async () => {
    expect(await runNumberingRequest("format", () => Promise.reject(new TypeError("x")), vi.fn())).toEqual({
      ok: false,
      rejected: false,
    });
  });
});
