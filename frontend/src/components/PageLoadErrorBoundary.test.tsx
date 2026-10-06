import { createInstance } from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider, initReactI18next } from "react-i18next";
import { describe, expect, it, vi } from "vitest";

import common from "../../public/locales/en/common.json";
import { PageLoadErrorBoundary, PageLoadErrorView } from "@/components/PageLoadErrorBoundary";

// Real translations; any key the view uses that is missing from the catalog is recorded so
// the test fails on it.
function render(node: React.ReactElement) {
  const missing: string[] = [];
  const i18n = createInstance();
  void i18n.use(initReactI18next).init({
    lng: "en",
    resources: { en: { common } },
    defaultNS: "common",
    initAsync: false,
    saveMissing: true,
    missingKeyHandler: (_lngs, ns, key) => missing.push(`${ns}:${key}`),
    interpolation: { escapeValue: false },
  });
  const html = renderToStaticMarkup(<I18nextProvider i18n={i18n}>{node}</I18nextProvider>);
  expect(missing).toEqual([]);
  return html;
}

describe("PageLoadErrorBoundary", () => {
  it("enters the error state when a child fails", () => {
    expect(PageLoadErrorBoundary.getDerivedStateFromError()).toEqual({ hasError: true });
  });

  it("renders its children when nothing failed", () => {
    const html = render(
      <PageLoadErrorBoundary>
        <p>the page</p>
      </PageLoadErrorBoundary>,
    );

    expect(html).toContain("the page");
    expect(html).not.toContain("couldn&#x27;t be loaded");
  });

  it("clears the error when the route changes, so other pages stay reachable", () => {
    const boundary = new PageLoadErrorBoundary({ children: null, resetKey: "/b" });
    boundary.state = { hasError: true };
    const setState = vi.spyOn(boundary, "setState").mockImplementation(() => undefined);

    boundary.componentDidUpdate({ children: null, resetKey: "/a" });

    expect(setState).toHaveBeenCalledWith({ hasError: false });
  });

  it("keeps the error while the route is the same", () => {
    const boundary = new PageLoadErrorBoundary({ children: null, resetKey: "/a" });
    boundary.state = { hasError: true };
    const setState = vi.spyOn(boundary, "setState").mockImplementation(() => undefined);

    boundary.componentDidUpdate({ children: null, resetKey: "/a" });

    expect(setState).not.toHaveBeenCalled();
  });

  it("does nothing on a route change when there was no error", () => {
    const boundary = new PageLoadErrorBoundary({ children: null, resetKey: "/b" });
    const setState = vi.spyOn(boundary, "setState").mockImplementation(() => undefined);

    boundary.componentDidUpdate({ children: null, resetKey: "/a" });

    expect(setState).not.toHaveBeenCalled();
  });
});

describe("PageLoadErrorView", () => {
  it("says the page could not be loaded and offers a Reload button", () => {
    const html = render(<PageLoadErrorView onReload={vi.fn()} />);

    expect(html).toContain("This page couldn&#x27;t be loaded");
    expect(html).toContain("The app may have been updated");
    expect(html).toMatch(/<button[^>]*>Reload<\/button>/);
    expect(html).toContain('role="alert"');
  });
});
