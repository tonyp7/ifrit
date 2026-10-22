import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { RowButton, RowLink } from "@/components/data-table/RowControl";

describe("RowLink", () => {
  it("is a real link to the row's page, stretched over the row", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <RowLink to="/projects/p1">Website redesign</RowLink>
      </MemoryRouter>,
    );
    expect(html).toContain("<a ");
    expect(html).toContain('href="/projects/p1"');
    expect(html).toContain(">Website redesign</a>");
    // The area over the row, so a click anywhere on it follows the link.
    expect(html).toContain("after:absolute");
    expect(html).toContain("after:inset-0");
  });

  it("can carry a name for a cell with no text", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <RowLink to="/invoices/i1" aria-label="Edit invoice for Website redesign" />
      </MemoryRouter>,
    );
    expect(html).toContain('aria-label="Edit invoice for Website redesign"');
    expect(html).toContain('href="/invoices/i1"');
  });
});

describe("RowButton", () => {
  it("is a button that opens a dialog, stretched over the row", () => {
    const html = renderToStaticMarkup(<RowButton onClick={vi.fn()}>Wire transfer</RowButton>);
    expect(html).toContain('<button type="button"');
    expect(html).toContain(">Wire transfer</button>");
    expect(html).toContain("after:absolute");
  });

  it("can carry a name too", () => {
    const html = renderToStaticMarkup(
      <RowButton onClick={vi.fn()} aria-label="Edit service line">
        —
      </RowButton>,
    );
    expect(html).toContain('aria-label="Edit service line"');
  });
});
