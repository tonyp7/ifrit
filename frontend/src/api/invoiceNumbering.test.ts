import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import { getNumbering, saveNumberingFormat, setNextNumber } from "@/api/invoiceNumbering";

vi.mock("@/api/client", () => ({ apiClient: { get: vi.fn(), put: vi.fn() } }));

beforeEach(() => vi.clearAllMocks());

describe("invoice numbering API", () => {
  it("reads, replaces the format and sets the next number", () => {
    const tokens = [{ type: "sequence" as const, digits: 4, start_at: 1, restart: "yearly" as const }];
    void getNumbering();
    void saveNumberingFormat(tokens, true);
    void setNextNumber(512);
    expect(apiClient.get).toHaveBeenCalledWith("/invoice-numbering");
    expect(apiClient.put).toHaveBeenCalledWith("/invoice-numbering", { tokens, confirm: true });
    expect(apiClient.put).toHaveBeenCalledWith("/invoice-numbering/next", { next_value: 512 });
  });
});
