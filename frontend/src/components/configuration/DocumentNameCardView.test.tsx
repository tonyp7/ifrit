import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  DocumentNameCardView,
  type DocumentNameCardViewProps,
} from "@/components/configuration/DocumentNameCardView";

const baseProps: DocumentNameCardViewProps = {
  loading: false,
  loadFailed: false,
  name: "Invoice",
  saving: false,
  onCommit: vi.fn(),
  onRetry: vi.fn(),
};

function render(overrides: Partial<DocumentNameCardViewProps> = {}) {
  return renderToStaticMarkup(<DocumentNameCardView {...baseProps} {...overrides} />);
}

function input(html: string): string {
  return /<input[^>]*>/.exec(html)?.[0] ?? "";
}

// The attribute, not the `disabled:` style variants in the class list.
function isDisabled(tag: string): boolean {
  return /\sdisabled=""/.test(tag);
}

describe("DocumentNameCardView", () => {
  it("shows the saved name in a labelled field capped at 60 characters", () => {
    const html = render({ name: "Tax Invoice" });

    expect(html).toContain("Document Name");
    expect(html).toContain("Document name");
    expect(input(html)).toContain('value="Tax Invoice"');
    expect(input(html)).toContain('maxLength="60"');
    expect(isDisabled(input(html))).toBe(false);
  });

  it("is empty and disabled while loading", () => {
    const tag = input(render({ loading: true, name: null }));

    expect(tag).toContain('value=""');
    expect(isDisabled(tag)).toBe(true);
  });

  it("is disabled while saving", () => {
    expect(isDisabled(input(render({ saving: true })))).toBe(true);
  });

  it("offers a retry after a failed load", () => {
    const html = render({ loadFailed: true, name: null });

    expect(html).toContain("Couldn&#x27;t load the document name.");
    expect(html).toContain("Try again");
  });
});
