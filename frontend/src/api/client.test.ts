import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, ApiError } from "@/api/client";
import { notifySessionExpired } from "@/api/sessionEvents";

vi.mock("@/api/sessionEvents", () => ({ notifySessionExpired: vi.fn() }));

type Scripted = { status: number; body?: unknown };

// A scripted stand-in for the browser's XMLHttpRequest: each instance answers with the
// next scripted response, after optionally reporting upload progress.
class FakeXhr {
  static instances: FakeXhr[] = [];
  static script: Scripted[] = [];
  static progress: [number, number][] = [];

  method = "";
  url = "";
  withCredentials = false;
  headers: Record<string, string> = {};
  sentBody: unknown = null;
  status = 0;
  responseText = "";
  upload: { onprogress: ((event: unknown) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  ontimeout: (() => void) | null = null;

  constructor() {
    FakeXhr.instances.push(this);
  }
  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }
  send(body: unknown) {
    this.sentBody = body;
    queueMicrotask(() => {
      for (const [loaded, total] of FakeXhr.progress) {
        this.upload.onprogress?.({ lengthComputable: true, loaded, total });
      }
      const next = FakeXhr.script.shift();
      if (!next) {
        this.onerror?.();
        return;
      }
      this.status = next.status;
      this.responseText = next.body === undefined ? "" : JSON.stringify(next.body);
      this.onload?.();
    });
  }
}

const fetchMock = vi.fn();

beforeEach(() => {
  FakeXhr.instances = [];
  FakeXhr.script = [];
  FakeXhr.progress = [];
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
  vi.mocked(notifySessionExpired).mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function form(): FormData {
  const body = new FormData();
  body.append("file", new Blob(["x"]), "logo.png");
  return body;
}

describe("apiClient.upload", () => {
  it("sends the form with credentials, the given method, and no JSON content type", async () => {
    FakeXhr.script = [{ status: 200, body: { file_id: "f1" } }];
    const body = form();

    const result = await apiClient.upload<{ file_id: string }>("/x", body, { method: "PUT" });

    expect(result).toEqual({ file_id: "f1" });
    const xhr = FakeXhr.instances[0];
    expect(xhr.method).toBe("PUT");
    expect(xhr.url).toBe("/api/x");
    expect(xhr.withCredentials).toBe(true);
    expect(xhr.sentBody).toBe(body);
    expect(Object.keys(xhr.headers)).not.toContain("Content-Type");
  });

  it("reports upload progress as whole percentages", async () => {
    FakeXhr.script = [{ status: 200, body: {} }];
    FakeXhr.progress = [
      [25, 100],
      [1, 3],
      [100, 100],
    ];
    const onProgress = vi.fn();

    await apiClient.upload("/x", form(), { onProgress });

    expect(onProgress.mock.calls.map((call) => call[0])).toEqual([25, 33, 100]);
  });

  it("refreshes the session once on a 401 and retries the upload", async () => {
    FakeXhr.script = [
      { status: 401, body: { detail: "Not authenticated" } },
      { status: 200, body: { file_id: "f2" } },
    ];
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));

    const result = await apiClient.upload<{ file_id: string }>("/x", form());

    expect(result).toEqual({ file_id: "f2" });
    expect(FakeXhr.instances).toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/auth/refresh");
    expect(notifySessionExpired).not.toHaveBeenCalled();
  });

  it("gives up and notifies when the refresh fails", async () => {
    FakeXhr.script = [{ status: 401, body: { detail: "Not authenticated" } }];
    fetchMock.mockResolvedValue(new Response("{}", { status: 401 }));

    await expect(apiClient.upload("/x", form())).rejects.toMatchObject({ status: 401 });

    expect(FakeXhr.instances).toHaveLength(1);
    expect(notifySessionExpired).toHaveBeenCalledTimes(1);
  });

  it("does not retry more than once", async () => {
    FakeXhr.script = [
      { status: 401, body: { detail: "no" } },
      { status: 401, body: { detail: "still no" } },
    ];
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));

    await expect(apiClient.upload("/x", form())).rejects.toMatchObject({ status: 401 });

    expect(FakeXhr.instances).toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("rejects with the server's message for a rejected upload", async () => {
    FakeXhr.script = [{ status: 415, body: { detail: "This file type is not allowed" } }];

    const failure = await apiClient.upload("/x", form()).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ status: 415, message: "This file type is not allowed" });
  });

  it("rejects with status 0 when the request never got a response", async () => {
    FakeXhr.script = [];

    await expect(apiClient.upload("/x", form())).rejects.toMatchObject({ status: 0 });
  });
});
