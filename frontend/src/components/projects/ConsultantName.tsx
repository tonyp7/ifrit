import { useTranslation } from "react-i18next";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { ServiceLineConsultant } from "@/types/project";

interface ConsultantNameProps {
  consultant: Pick<ServiceLineConsultant, "full_name" | "is_active">;
}

/**
 * A consultant's name. A since-deleted user (still on the service line as history) is
 * shown in red with a "no longer exists" tooltip — they can only be removed, never
 * saved back onto a line.
 */
export function ConsultantName({ consultant }: ConsultantNameProps) {
  const { t } = useTranslation(["projects"]);

  if (consultant.is_active) return <>{consultant.full_name}</>;

  // Own provider: only NavBar mounts one, and this renders inside dialogs/tables.
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="text-destructive" tabIndex={0}>
            {consultant.full_name}
          </span>
        </TooltipTrigger>
        <TooltipContent>{t("This user no longer exists")}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
