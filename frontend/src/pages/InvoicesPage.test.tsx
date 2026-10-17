import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { InvoicesPage } from "@/pages/InvoicesPage";

describe("InvoicesPage", () => {
  it("shows the empty state and no create action", () => {
    const html = renderToStaticMarkup(<InvoicesPage />);

    expect(html).toContain("No invoices yet");
    expect(html).not.toContain("<button");
    expect(html).not.toContain("<a ");
  });
});
