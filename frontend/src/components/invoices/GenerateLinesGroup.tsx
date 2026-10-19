import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

interface GenerateLinesGroupProps {
  /** What to bill: the service lines and period, or the milestones. */
  children: ReactNode;
  canGenerate: boolean;
  generating: boolean;
  onGenerate: () => void;
}

/** The choice of what to bill with the button that turns it into lines, directly under it. */
export function GenerateLinesGroup({
  children,
  canGenerate,
  generating,
  onGenerate,
}: GenerateLinesGroupProps) {
  const { t } = useTranslation(["invoices"]);
  return (
    <fieldset className="flex flex-col gap-4 rounded-md border p-4">
      <legend className="px-1 text-sm font-medium">{t("Generate line items")}</legend>
      {children}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="outline" disabled={!canGenerate} onClick={onGenerate}>
          {generating && <Spinner />}
          {generating ? t("Generating…") : t("Generate line items")}
        </Button>
      </div>
    </fieldset>
  );
}
