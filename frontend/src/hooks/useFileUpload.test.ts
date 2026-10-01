import { describe, expect, it } from "vitest";

import { ApiError } from "@/api/client";
import {
  initialUploadState,
  runUpload,
  uploadReducer,
  type UploadAction,
  type UploadState,
} from "@/hooks/useFileUpload";

// Replays the dispatched actions through the reducer, like the hook does.
async function run(send: Parameters<typeof runUpload>[0]) {
  const actions: UploadAction[] = [];
  let state: UploadState = initialUploadState;
  const result = await runUpload(send, (action) => {
    actions.push(action);
    state = uploadReducer(state, action);
  });
  return { result, actions, state };
}

describe("runUpload", () => {
  it("goes idle -> uploading (with progress) -> ready on success", async () => {
    const { result, actions, state } = await run(async (onProgress) => {
      onProgress(40);
      onProgress(100);
      return { file_id: "f1" };
    });

    expect(result).toEqual({ file_id: "f1" });
    expect(actions.map((action) => action.type)).toEqual([
      "start",
      "progress",
      "progress",
      "success",
    ]);
    expect(state).toEqual({ status: "ready", progress: 100, fileId: "f1", error: null });
  });

  it("treats a 4xx as rejected, keeping the server's reason", async () => {
    const { result, state } = await run(async () => {
      throw new ApiError(415, "This file type is not allowed");
    });

    expect(result).toBeNull();
    expect(state.status).toBe("rejected");
    expect(state.error).toBe("This file type is not allowed");
  });

  it("treats a network failure as an error, distinct from a rejection", async () => {
    const { state } = await run(async () => {
      throw new ApiError(0, "Network error");
    });

    expect(state.status).toBe("error");
    expect(state.error).toBe("Network error");
  });

  it("treats a server error as an error, not a rejection", async () => {
    const { state } = await run(async () => {
      throw new ApiError(500, "Request failed with status 500");
    });

    expect(state.status).toBe("error");
  });

  it("treats any other thrown value as an error", async () => {
    const { state } = await run(async () => {
      throw new Error("boom");
    });

    expect(state).toMatchObject({ status: "error", error: "boom" });
  });
});

describe("uploadReducer", () => {
  it("ignores late progress once the upload has finished", () => {
    const done = uploadReducer(initialUploadState, { type: "success", fileId: "f1" });

    expect(uploadReducer(done, { type: "progress", progress: 12 })).toBe(done);
  });

  it("clears a previous failure when a new upload starts", () => {
    const failed = uploadReducer(initialUploadState, { type: "rejected", message: "no" });

    expect(uploadReducer(failed, { type: "start" })).toEqual({
      status: "uploading",
      progress: 0,
      fileId: null,
      error: null,
    });
  });

  it("returns to idle on reset", () => {
    const failed = uploadReducer(initialUploadState, { type: "error", message: "x" });

    expect(uploadReducer(failed, { type: "reset" })).toEqual(initialUploadState);
  });
});
