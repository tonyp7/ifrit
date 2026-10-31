import { createContext, useContext, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ExportMenu } from "@/components/reporting/ExportMenu";

// Radix mounts menu content in a portal only while open, which a markup test never reaches, so
// the menu primitives render inline, keeping the roles and the selected value the test reads.
vi.mock("@/components/ui/dropdown-menu", () => {
  const Inline = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
  const Selected = createContext<string | undefined>(undefined);
  return {
    DropdownMenu: Inline,
    DropdownMenuTrigger: Inline,
    DropdownMenuContent: Inline,
    DropdownMenuItem: ({ children }: { children?: ReactNode }) => (
      <div role="menuitem">{children}</div>
    ),
    DropdownMenuSeparator: () => <hr role="separator" />,
    DropdownMenuLabel: ({ children }: { children?: ReactNode }) => (
      <div role="presentation">{children}</div>
    ),
    DropdownMenuRadioGroup: ({
      value,
      children,
    }: {
      value?: string;
      children?: ReactNode;
    }) => (
      <Selected.Provider value={value}>
        <div role="group">{children}</div>
      </Selected.Provider>
    ),
    DropdownMenuRadioItem: function RadioItem({
      value,
      children,
    }: {
      value: string;
      children?: ReactNode;
    }) {
      return (
        <div role="menuitemradio" aria-checked={useContext(Selected) === value}>
          {children}
        </div>
      );
    },
  };
});

// Rendered with the global English i18n instance (src/test/setup.ts), which fails the test on
// any key missing from public/locales/en.
function render(exportingFormat: "pdf" | "xlsx" | "csv" | null = null) {
  return renderToStaticMarkup(
    <ExportMenu exportingFormat={exportingFormat} onExport={vi.fn()} />,
  );
}

function inOrder(html: string, ...markers: string[]): boolean {
  let at = -1;
  for (const marker of markers) {
    at = html.indexOf(marker, at + 1);
    if (at < 0) return false;
  }
  return true;
}

describe("ExportMenu", () => {
  it("lists the three formats, then a separator, the Export as… label and the two units", () => {
    expect(
      inOrder(
        render(),
        ">Export as PDF<",
        ">Export as Excel<",
        ">Export as CSV<",
        'role="separator"',
        ">Export as…<",
        ">Hours<",
        ">Days<",
      ),
    ).toBe(true);
  });

  it("starts on Hours", () => {
    const html = render();

    expect(html).toMatch(/aria-checked="true">Hours</);
    expect(html).toMatch(/aria-checked="false">Days</);
    expect(html.match(/aria-checked="true"/g)).toHaveLength(1);
  });

  it("shows the exporting state and disables the button while a file is being made", () => {
    const html = render("xlsx");

    expect(html).toContain("Exporting…");
    expect(html).toMatch(/<button[^>]*\sdisabled=""/);
  });

  it("offers a ready button when nothing is being exported", () => {
    const html = render();

    expect(html).toContain(">Export<");
    expect(html).not.toMatch(/<button[^>]*\sdisabled=""/);
  });
});
