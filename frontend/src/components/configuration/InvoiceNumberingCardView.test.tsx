import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  InvoiceNumberingCardView,
  type InvoiceNumberingCardViewProps,
} from "@/components/configuration/InvoiceNumberingCardView";
import { DEFAULT_TOKENS, initialEditorState } from "@/lib/invoiceNumbering";
import type { NumberingState, NumberingToken } from "@/types/invoiceNumbering";

const saved: NumberingState = {
  tokens: DEFAULT_TOKENS,
  next_value: 43,
  preview: [],
  has_issued: false,
};

function render(
  tokens: NumberingToken[] = DEFAULT_TOKENS,
  overrides: Partial<InvoiceNumberingCardViewProps> = {},
) {
  const props: InvoiceNumberingCardViewProps = {
    loading: false,
    loadFailed: false,
    saved,
    editor: initialEditorState(tokens),
    dispatch: vi.fn(),
    busy: null,
    today: new Date(2026, 9, 14),
    onSave: vi.fn(),
    onRetry: vi.fn(),
    nextNumber: "43",
    onNextNumberChange: vi.fn(),
    onSetNext: vi.fn(),
    nextError: null,
    ...overrides,
  };
  return renderToStaticMarkup(<InvoiceNumberingCardView {...props} />);
}

describe("InvoiceNumberingCardView", () => {
  it("shows presets, tiles, the format, the preview and the reset note", () => {
    const html = render();
    expect(html).toContain("Invoice Numbering");
    for (const preset of ["INV-00001", "2026-0001", "202610-001"])
      expect(html).toContain(preset);
    expect(html).toContain("INV-2026-0043 → INV-2026-0044 → INV-2026-0045");
    expect(html).toContain("Counter resets every January 1.");
    expect(html).toContain("Sequence · 4 digits · yearly");
    expect(html).toContain('aria-live="polite"');
  });

  it("marks the Sequence tile as used when the format has one", () => {
    expect(render()).toContain('aria-description="Already in the format"');
    expect(render([{ type: "year" }])).not.toContain("Already in the format");
  });

  it("shows the empty state with no tokens", () => {
    const html = render([]);
    expect(html).toContain("Click a tile to start building your format.");
    expect(html).not.toContain("or type");
  });

  it("lists the tiles in three groups: dates, Sequence, Label", () => {
    const html = render([]);
    const names = ["Year", "Month", "Day", "Sequence #", "Label"];
    const positions = names.map((name) => html.indexOf(`>${name}<`));
    expect(positions.every((position) => position > -1)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
    // One divider between the dates and Sequence, one between Sequence and Label.
    expect(html.match(/bg-border mx-1 h-6 w-px/g)).toHaveLength(2);
  });

  it("shows fixed text as Label chips with a text box, a grip and a remove button", () => {
    const html = render();
    expect(html).toContain('value="INV-"');
    expect(html).toContain('value="-"');
    expect(html).toContain('aria-label="Label text"');
    expect(html).toContain('aria-label="Move the label INV-"');
    expect(html).toContain('aria-label="Remove INV-"');
    expect(html).toContain('aria-label="Remove -"');
  });

  it("loads a preset's text as a Label chip too", () => {
    const html = render([
      { type: "text", value: "INV-" },
      { type: "sequence", digits: 5, start_at: 1, restart: "never" },
    ]);
    expect(html).toContain('aria-label="Remove INV-"');
    expect(html).toContain("Sequence · 5 digits · never restarts");
  });

  it("previews two adjacent Labels as one text", () => {
    const html = render([
      { type: "text", value: "-" },
      { type: "text", value: "-" },
      { type: "sequence", digits: 4, start_at: 1, restart: "never" },
    ]);
    expect(html).toContain("--0001");
  });

  it("flags a bad character in a Label and disables Save", () => {
    const html = render([
      { type: "text", value: "INV#" },
      { type: "sequence", digits: 4, start_at: 1, restart: "never" },
    ]);
    expect(html).toContain("Only letters, numbers, -, / and _ are allowed.");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Save</);
  });

  it("shows an error and disables Save without a sequence", () => {
    const html = render([{ type: "text", value: "INV-" }]);
    expect(html).toContain("Invoice numbers may not be unique. Add a sequence.");
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>Save</);
  });

  it("warns about a counter restarting without its date tiles, without blocking", () => {
    const html = render([
      { type: "text", value: "INV-" },
      { type: "year" },
      { type: "sequence", digits: 4, start_at: 1, restart: "monthly" },
    ]);
    expect(html).toContain(
      "This counter restarts monthly, so numbers will repeat across months.",
    );
    expect(html).toContain("The new restart period starts its own counter.");
  });

  it("shows the next number with its inline error", () => {
    const html = render(DEFAULT_TOKENS, {
      nextError: "The number INV-2026-0007 already exists",
    });
    expect(html).toContain('value="43"');
    expect(html).toContain("The number INV-2026-0007 already exists");
  });

  it("offers a retry after a failed load", () => {
    const html = render(DEFAULT_TOKENS, { loadFailed: true, saved: null });
    expect(html).toContain("Couldn&#x27;t load the invoice numbering.");
  });
});
