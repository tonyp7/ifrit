import i18n from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import {
  ProjectsTableView,
  type ProjectsTableViewProps,
} from "@/components/projects/ProjectsTable";
import type { ProjectListItem } from "@/types/project";

const project: ProjectListItem = {
  id: "p1",
  name: "Website redesign",
  status: "active",
  project_type: "fixed_price",
  client_company_id: "c1",
  client_company_name: "ACME",
  vendor_company_id: "c2",
  vendor_company_name: "Apex Solutions",
  created_at: "2026-10-14T09:00:00Z",
};

// vendor_company_name is opt-in, hidden until the "Columns" button shows it.
const DEFAULT_VISIBILITY = { vendor_company_name: false };

function render(items: ProjectListItem[], columnVisibility = DEFAULT_VISIBILITY) {
  const props: ProjectsTableViewProps = {
    items,
    sorting: [],
    onSortingChange: vi.fn(),
    pageCount: 1,
    columnVisibility,
    onColumnVisibilityChange: vi.fn(),
    onOpen: vi.fn(),
    onDuplicate: vi.fn(),
    onDelete: vi.fn(),
  };
  // The name is a link, which needs a router.
  return renderToStaticMarkup(
    <MemoryRouter>
      <ProjectsTableView {...props} />
    </MemoryRouter>,
  );
}

describe("ProjectsTableView", () => {
  it("shows the empty state", () => {
    expect(render([])).toContain("No projects found.");
  });

  it("shows the default columns in order, without Vendor", () => {
    const html = render([project]);
    const headers = ["Name", "Status", "Client", "Project Type", "Creation Date"];
    const positions = headers.map((header) => html.indexOf(`>${header}<`));
    expect(positions.every((position) => position > -1)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
    expect(html).not.toContain(">Vendor<");
    expect(html).not.toContain("Apex Solutions");
  });

  it("shows the Vendor column when it is switched on", () => {
    const html = render([project], { vendor_company_name: true });
    expect(html).toContain(">Vendor<");
    expect(html).toContain("Apex Solutions");
  });

  it("links the name to the project's form and shows its status, type and date", () => {
    const html = render([project]);
    expect(html).toContain('href="/projects/p1"');
    expect(html).toContain("Website redesign");
    expect(html).toContain(">Active<");
    expect(html).toContain("Fixed Price");
    expect(html).toContain("10/14/2026");
  });

  it("shows a dash for a missing client", () => {
    expect(render([{ ...project, client_company_name: null }])).toContain("—");
  });

  it("shows French headers, status, type and date when the language is French", async () => {
    await i18n.changeLanguage("fr");
    const html = render([project]);
    for (const text of [
      "Nom",
      "Statut",
      "Type de projet",
      "Date de création",
      ">Actif<",
      "Forfait",
    ]) {
      expect(html).toContain(text);
    }
    expect(html).toContain("14/10/2026");
    expect(html).not.toContain("10/14/2026");
    expect(render([])).toContain("Aucun projet trouvé.");
  });
});
