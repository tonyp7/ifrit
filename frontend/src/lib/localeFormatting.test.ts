import i18n from "i18next";
import { afterEach, describe, expect, it } from "vitest";

import { formatDueDate } from "@/lib/billingMilestones";
import {
  formatMoney,
  formatMoneyInput,
  formatQuantity,
  formatQuantityInput,
  stripGrouping,
} from "@/lib/format";
import { formatPeriod } from "@/lib/invoicePeriods";
import { formatHours, formatHoursDisplay } from "@/lib/timesheetHours";
import {
  formatFullDate,
  formatMonthLabel,
  formatWeekdayNarrow,
  formatWeekdayShort,
  getIsoWeekNumber,
  startOfWeekMonday,
} from "@/lib/timesheetDates";

// Intl separates French thousands with a narrow no-break space; compare with a plain one.
const plain = (text: string) => text.replace(new RegExp("[\\u202f\\u00a0]", "g"), " ");

async function inFrench(check: () => void) {
  await i18n.changeLanguage("fr");
  check();
}

describe("formatting follows the app language", () => {
  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  it("formats amounts in English", () => {
    expect(formatMoney("1234.5", 2)).toBe("1,234.50");
    expect(formatQuantity("1234.5")).toBe("1,234.5");
  });

  it("formats amounts in French: space for thousands, comma for decimals", async () => {
    await inFrench(() => {
      expect(plain(formatMoney("1234.5", 2))).toBe("1 234,50");
      expect(plain(formatMoney("1234", 0))).toBe("1 234");
      expect(plain(formatQuantity("1234.5"))).toBe("1 234,5");
    });
  });

  it("changes the result as soon as the language is switched", async () => {
    expect(formatMoney("1234.5", 2)).toBe("1,234.50");
    await i18n.changeLanguage("fr");
    expect(formatMoney("1234.5", 2)).not.toBe("1,234.50");
    await i18n.changeLanguage("en");
    expect(formatMoney("1234.5", 2)).toBe("1,234.50");
  });

  it("formats dates and periods in the language", async () => {
    expect(formatDueDate("2027-01-15")).toBe("Jan 15, 2027");
    expect(formatPeriod(new Date(2026, 8, 1), new Date(2026, 8, 30))).toContain("Sep");
    await inFrench(() => {
      expect(formatDueDate("2027-01-15")).toBe("15 janv. 2027");
      expect(formatPeriod(new Date(2026, 8, 1), new Date(2026, 8, 30))).toContain("sept.");
    });
  });

  it("names months and weekdays in the language", async () => {
    const monday = new Date(2026, 9, 12);
    expect(formatMonthLabel(monday)).toBe("October 2026");
    expect(formatWeekdayShort(monday)).toBe("Mon");
    await inFrench(() => {
      expect(formatMonthLabel(monday)).toBe("octobre 2026");
      expect(formatWeekdayShort(monday)).toBe("lun");
      expect(formatWeekdayNarrow(monday)).toBe("L");
      expect(formatFullDate(monday)).toBe("lundi 12 octobre");
    });
  });

  it("starts the week on Monday in both languages", async () => {
    const wednesday = new Date(2026, 9, 14);
    expect(startOfWeekMonday(wednesday).getDay()).toBe(1);
    expect(getIsoWeekNumber(wednesday)).toBe(42);
    await inFrench(() => {
      expect(startOfWeekMonday(wednesday).getDay()).toBe(1);
      expect(getIsoWeekNumber(wednesday)).toBe(42);
    });
  });
});

describe("hours totals", () => {
  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  it("uses the decimal mark of the language and shows 0 for nothing", async () => {
    expect(formatHoursDisplay(7.5)).toBe("7.5");
    expect(formatHoursDisplay(8)).toBe("8");
    expect(formatHoursDisplay(0)).toBe("0");
    await inFrench(() => {
      expect(formatHoursDisplay(7.5)).toBe("7,5");
      expect(formatHoursDisplay(8)).toBe("8");
      expect(formatHoursDisplay(0)).toBe("0");
    });
  });

  it("keeps the edited form of an hours value with a period", async () => {
    await inFrench(() => {
      expect(formatHours(7.5)).toBe("7.5");
    });
  });
});

describe("editable fields keep the English form", () => {
  afterEach(async () => {
    await i18n.changeLanguage("en");
  });

  it("pre-fills the same text in English and French, and it parses back", async () => {
    const english = [formatMoneyInput("1234.5", 2), formatQuantityInput("1234.5")];
    expect(english).toEqual(["1,234.50", "1,234.5"]);
    await inFrench(() => {
      expect([formatMoneyInput("1234.5", 2), formatQuantityInput("1234.5")]).toEqual(english);
    });
    expect(stripGrouping(english[0])).toBe("1234.50");
    expect(stripGrouping(english[1])).toBe("1234.5");
  });

  it("leaves a value that is not a number as it is", () => {
    expect(formatMoneyInput("abc", 2)).toBe("abc");
  });
});
