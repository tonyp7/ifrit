import { useCallback, useReducer } from "react";

import { ApiError } from "@/api/client";

// "scanning" and "processing" are not here yet: uploads are validated inside the request,
// so there is no post-upload phase to report. They arrive with background scanning.
export type UploadStatus = "idle" | "uploading" | "ready" | "rejected" | "error";

export interface UploadState {
  status: UploadStatus;
  /** 0-100, from the browser's own count of bytes sent. */
  progress: number;
  /** Id of the stored file once `ready`. */
  fileId: string | null;
  /** The server's reason when `rejected`, a generic message when `error`. */
  error: string | null;
}

export const initialUploadState: UploadState = {
  status: "idle",
  progress: 0,
  fileId: null,
  error: null,
};

export type UploadAction =
  | { type: "start" }
  | { type: "progress"; progress: number }
  | { type: "success"; fileId: string }
  | { type: "rejected"; message: string }
  | { type: "error"; message: string }
  | { type: "reset" };

export function uploadReducer(state: UploadState, action: UploadAction): UploadState {
  switch (action.type) {
    case "start":
      return { status: "uploading", progress: 0, fileId: null, error: null };
    case "progress":
      // Late progress events after the request finished must not revive the bar.
      return state.status === "uploading" ? { ...state, progress: action.progress } : state;
    case "success":
      return { status: "ready", progress: 100, fileId: action.fileId, error: null };
    case "rejected":
      return { status: "rejected", progress: 0, fileId: null, error: action.message };
    case "error":
      return { status: "error", progress: 0, fileId: null, error: action.message };
    case "reset":
      return initialUploadState;
  }
}

/**
 * Runs one upload and reports it as state transitions. A 4xx answer means the server
 * looked at the file and refused it (`rejected`, with its reason); anything else, such as
 * a dropped connection or a 5xx, says nothing about the file itself (`error`, retryable).
 * Returns the server's response on success, null otherwise.
 */
export async function runUpload<T extends { file_id: string }>(
  send: (onProgress: (percent: number) => void) => Promise<T>,
  dispatch: (action: UploadAction) => void,
): Promise<T | null> {
  dispatch({ type: "start" });
  try {
    const result = await send((progress) => dispatch({ type: "progress", progress }));
    dispatch({ type: "success", fileId: result.file_id });
    return result;
  } catch (failure) {
    if (failure instanceof ApiError && failure.status >= 400 && failure.status < 500) {
      dispatch({ type: "rejected", message: failure.message });
    } else {
      dispatch({
        type: "error",
        message: failure instanceof Error ? failure.message : "Upload failed",
      });
    }
    return null;
  }
}

/**
 * Upload state for one file upload. One hook instance per upload, so concurrent uploads
 * are tracked independently. Components never touch XMLHttpRequest themselves.
 */
export function useFileUpload<T extends { file_id: string }>(
  send: (file: File, onProgress: (percent: number) => void) => Promise<T>,
) {
  const [state, dispatch] = useReducer(uploadReducer, initialUploadState);

  const upload = useCallback(
    (file: File) => runUpload((onProgress) => send(file, onProgress), dispatch),
    [send],
  );
  const reset = useCallback(() => dispatch({ type: "reset" }), []);

  return { ...state, upload, reset };
}
