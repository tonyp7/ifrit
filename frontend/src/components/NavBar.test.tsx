import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { NavBar } from "@/components/NavBar";

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    user: { roles: ["administrator", "project_admin", "project_manager"] },
    logout: vi.fn(),
  }),
}));
vi.mock("@/hooks/useTheme", () => ({
  useTheme: () => ({ themePreference: "system", setThemePreference: vi.fn() }),
}));

// Labels (the sr-only text) of the icons NavLink marked as the current page.
function highlighted(path: string): string[] {
  const html = renderToStaticMarkup(
    <MemoryRouter initialEntries={[path]}>
      <NavBar />
    </MemoryRouter>,
  );
  return [...html.matchAll(/<a [^>]*aria-current="page"[^>]*>.*?sr-only">([^<]+)</g)].map(
    (match) => match[1],
  );
}

describe("nav bar highlight", () => {
  it("highlights only Timesheet on /", () => {
    expect(highlighted("/")).toEqual(["Timesheet"]);
  });

  it("highlights Configuration on every configuration screen, nested ones included", () => {
    for (const path of [
      "/configuration/general",
      "/configuration/users",
      "/configuration/users/new",
      "/configuration/companies/42",
    ]) {
      expect(highlighted(path)).toEqual(["Configuration"]);
    }
  });

  it("highlights Projects on a project's edit and create screens", () => {
    expect(highlighted("/projects/42")).toEqual(["Projects"]);
    expect(highlighted("/projects/new")).toEqual(["Projects"]);
  });

  it("renders the Configuration icon as a plain link to /configuration", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/"]}>
        <NavBar />
      </MemoryRouter>,
    );
    expect(html).toContain('href="/configuration"');
  });
});
