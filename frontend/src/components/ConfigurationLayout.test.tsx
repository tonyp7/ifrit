import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import { ConfigurationLayout } from "@/components/ConfigurationLayout";
import { configurationTabForPath } from "@/config/configurationTabs";

function render(path: string): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/configuration" element={<ConfigurationLayout />}>
          <Route path="general" element={<p>general body</p>} />
          <Route path="companies/:companyId" element={<p>company body</p>} />
          <Route path="users/new" element={<p>new user body</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

// [href, label, active] of every tab rendered in the layout.
function tabs(html: string): [string, string, boolean][] {
  return [...html.matchAll(/<a [^>]*>/g)].map((anchor) => {
    const tag = anchor[0];
    const label = html.slice(anchor.index + tag.length).split("<")[0];
    return [/href="([^"]+)"/.exec(tag)?.[1] ?? "", label, tag.includes('data-state="active"')];
  });
}

describe("ConfigurationLayout", () => {
  it("renders General, Companies and Users as links, in that order", () => {
    expect(
      tabs(render("/configuration/general")).map(([href, label]) => [href, label]),
    ).toEqual([
      ["/configuration/general", "General"],
      ["/configuration/companies", "Companies"],
      ["/configuration/users", "Users"],
    ]);
  });

  it("marks General active and shows its screen", () => {
    const html = render("/configuration/general");
    expect(tabs(html).map(([, , active]) => active)).toEqual([true, false, false]);
    expect(html).toContain("general body");
  });

  it("keeps Companies active on a company's edit screen", () => {
    const html = render("/configuration/companies/42");
    expect(tabs(html).map(([, , active]) => active)).toEqual([false, true, false]);
    expect(html).toContain("company body");
  });

  it("keeps Users active on the new-user screen", () => {
    const html = render("/configuration/users/new");
    expect(tabs(html).map(([, , active]) => active)).toEqual([false, false, true]);
    expect(html).toContain("new user body");
  });
});

describe("configurationTabForPath", () => {
  it("maps nested paths to their section's tab", () => {
    expect(configurationTabForPath("/configuration/companies/42")).toBe("companies");
    expect(configurationTabForPath("/configuration/users/new")).toBe("users");
  });

  it("returns undefined for the bare path and unknown sections", () => {
    expect(configurationTabForPath("/configuration")).toBeUndefined();
    expect(configurationTabForPath("/configuration/unknown")).toBeUndefined();
  });
});
