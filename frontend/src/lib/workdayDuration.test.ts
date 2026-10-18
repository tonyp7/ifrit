import { describe, expect, it } from "vitest";

import {
  formatDuration,
  joinDuration,
  parsePart,
  PART_MAX,
  splitDuration,
} from "@/lib/workdayDuration";

describe("workday duration", () => {
  it("splits a total into hours, minutes and seconds", () => {
    expect(splitDuration(28800)).toEqual({ hours: 8, minutes: 0, seconds: 0 });
    expect(splitDuration(86400)).toEqual({ hours: 24, minutes: 0, seconds: 0 });
    expect(splitDuration(3725)).toEqual({ hours: 1, minutes: 2, seconds: 5 });
  });

  it("keeps the bounds as they are", () => {
    expect(joinDuration({ hours: 0, minutes: 30, seconds: 0 })).toBe(1800);
    expect(joinDuration({ hours: 24, minutes: 0, seconds: 0 })).toBe(86400);
  });

  it("brings a length above 24 hours down to 24:00:00", () => {
    expect(joinDuration({ hours: 24, minutes: 30, seconds: 0 })).toBe(86400);
  });

  it("brings a length below 30 minutes up to 00:30:00", () => {
    expect(joinDuration({ hours: 0, minutes: 10, seconds: 0 })).toBe(1800);
  });

  it("lowers a field above its maximum and treats junk as 0", () => {
    expect(parsePart("75", PART_MAX.minutes)).toBe(59);
    expect(parsePart("30", PART_MAX.hours)).toBe(24);
    expect(parsePart("", PART_MAX.hours)).toBe(0);
    expect(parsePart("-3", PART_MAX.hours)).toBe(0);
    expect(parsePart("1.5", PART_MAX.hours)).toBe(0);
  });

  it("formats as hh:mm:ss", () => {
    expect(formatDuration(1800)).toBe("00:30:00");
    expect(formatDuration(86400)).toBe("24:00:00");
  });
});
