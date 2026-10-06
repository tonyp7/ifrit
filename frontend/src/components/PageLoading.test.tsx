import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PageLoading } from "@/components/PageLoading";

describe("PageLoading", () => {
  it("shows a spinner announced as a status", () => {
    const html = renderToStaticMarkup(<PageLoading />);

    expect(html).toContain('role="status"');
    expect(html).toContain("animate-spin");
  });

  it("reserves vertical room so the page around it does not collapse", () => {
    const html = renderToStaticMarkup(<PageLoading />);

    expect(html).toMatch(/min-h-\[40vh\]/);
  });
});
