import { describe, expect, it } from "vitest";

import { formatFileSize } from "@/lib/format";

describe("formatFileSize", () => {
  it("shows bytes below a kilobyte without decimals", () => {
    expect(formatFileSize(0)).toBe("0 B");
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(999)).toBe("999 B");
  });

  it("uses decimal units with at most one decimal", () => {
    expect(formatFileSize(1000)).toBe("1 KB");
    expect(formatFileSize(1400)).toBe("1.4 KB");
    expect(formatFileSize(2_100_000)).toBe("2.1 MB");
    expect(formatFileSize(10_485_760)).toBe("10.5 MB");
  });

  it("is empty for a size that cannot be real", () => {
    expect(formatFileSize(-1)).toBe("");
    expect(formatFileSize(Number.NaN)).toBe("");
  });
});
