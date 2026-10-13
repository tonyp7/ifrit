import { renderToStaticMarkup } from "react-dom/server";
import { StaticRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { ProjectFormPage } from "@/pages/ProjectFormPage";

function renderPage() {
  return renderToStaticMarkup(
    <StaticRouter location="/projects/new">
      <ProjectFormPage />
    </StaticRouter>,
  );
}

describe("ProjectFormPage", () => {
  it("places the project references between the header fields and the project managers", () => {
    const html = renderPage();

    const header = html.indexOf("Invoicing currency");
    const references = html.indexOf("Project References");
    const managers = html.indexOf("Project Managers");
    const serviceLines = html.indexOf("Service Lines");

    expect(header).toBeGreaterThan(-1);
    expect(references).toBeGreaterThan(header);
    expect(managers).toBeGreaterThan(references);
    if (serviceLines !== -1) expect(serviceLines).toBeGreaterThan(managers);
  });

  it("offers Add and no table on a new project", () => {
    const html = renderPage();

    const section = html.slice(
      html.indexOf("Project References"),
      html.indexOf("Project Managers"),
    );
    expect(section).toContain("Add");
    expect(section).not.toContain("<table");
  });
});
