import { useTranslation } from "react-i18next";

import { formatMoney } from "@/lib/format";
import { UOM_LABELS, type Uom } from "@/types/project";

/** A service line by its name, or by its unit and price when it has none. */
export function useServiceLineLabel(minorUnit: number | null) {
  const { t } = useTranslation(["invoices", "projects"]);
  return (line: { name: string | null; uom: Uom; unit_price: string }) =>
    line.name ||
    t("{{unit}} at {{price}}", {
      unit: t(UOM_LABELS[line.uom], { ns: "projects" }),
      price: formatMoney(line.unit_price, minorUnit),
    });
}
