import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ServiceLineFormDialog } from "@/components/projects/ServiceLineFormDialog";
import type { ServiceLineConsultant } from "@/types/project";

// Radix renders a dialog through a portal, which server rendering leaves empty: render its
// parts inline so the dialog's body is checked. Server rendering shows the first render, which
// is what the consultants regression is about.
vi.mock("@/components/ui/dialog", () => {
  const Inline = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
  return {
    Dialog: Inline,
    DialogContent: Inline,
    DialogHeader: Inline,
    DialogFooter: Inline,
    DialogTitle: Inline,
  };
});

const john: ServiceLineConsultant = { id: "u1", full_name: "John Wayne", is_active: true };
const gone: ServiceLineConsultant = { id: "u2", full_name: "Jane Doe", is_active: false };

function render(initialConsultants?: ServiceLineConsultant[]) {
  return renderToStaticMarkup(
    <ServiceLineFormDialog
      open
      onOpenChange={vi.fn()}
      projectId="p1"
      serviceLineId={initialConsultants ? "l1" : undefined}
      initialValues={
        initialConsultants
          ? {
              name: "Tech Lead",
              quantity: "1",
              uom: "days",
              unit_price: "800",
              user_ids: initialConsultants.map((c) => c.id),
            }
          : undefined
      }
      initialConsultants={initialConsultants}
      onSaved={vi.fn()}
      minorUnit={2}
    />,
  );
}

describe("ServiceLineFormDialog consultants", () => {
  it("shows the line's consultants as chips with a remove button when opened to edit", () => {
    const html = render([john]);
    expect(html).toContain("John Wayne");
    expect(html).toContain("Remove John Wayne");
  });

  it("shows every consultant of the line", () => {
    const html = render([john, { id: "u3", full_name: "Ada Lovelace", is_active: true }]);
    expect(html).toContain("Remove John Wayne");
    expect(html).toContain("Remove Ada Lovelace");
  });

  it("shows no chips for a new service line", () => {
    const html = render(undefined);
    expect(html).not.toContain("Remove ");
    expect(html).toContain("Select consultants…");
  });

  it("keeps a deleted consultant as a chip and asks for their removal", () => {
    const html = render([john, gone]);
    expect(html).toContain("Remove Jane Doe");
    expect(html).toContain("Remove deleted consultants before saving.");
  });
});
