import { useId } from "react";
import { useTranslation } from "react-i18next";

import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

// "Only see my projects", shared by Reporting and Projects. A view choice only:
// every manager may open every project, so this narrows what is listed, not what
// is allowed. Switch first, label beside it, like the app's other switches.
export function MineOnlySwitch({
  checked,
  onCheckedChange,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  const { t } = useTranslation("common");
  const id = useId();
  return (
    <div className="flex items-center gap-2">
      <Switch id={id} checked={checked} onCheckedChange={onCheckedChange} />
      <Label htmlFor={id} className="whitespace-nowrap">
        {t("Only see my projects")}
      </Label>
    </div>
  );
}
