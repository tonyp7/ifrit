import { InfoIcon, TriangleAlertIcon } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import type { BannerColor, BannerIcon } from "@/types/settings";

export interface InformationBannerProps {
  message: string;
  icon: BannerIcon;
  color: BannerColor;
  className?: string;
}

// Tinted surface, border and text per color, each with a dark-theme counterpart. The icon
// takes the text color (the Alert primitive would otherwise paint it with the foreground).
const COLOR_CLASSES: Record<BannerColor, string> = {
  neutral: "border-border bg-muted text-foreground",
  blue: "border-blue-300 bg-blue-50 text-blue-900 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-100",
  yellow:
    "border-yellow-400 bg-yellow-50 text-yellow-900 dark:border-yellow-700 dark:bg-yellow-950 dark:text-yellow-100",
  red: "border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-100",
};

/**
 * The administrator's notice, shown on the sign-in page, across the top of every signed-in
 * page, and as the preview in the settings card. The message is plain text: it is rendered
 * as a text child (never as markup) and keeps its line breaks.
 */
export function InformationBanner({
  message,
  icon,
  color,
  className,
}: InformationBannerProps) {
  return (
    // A notice that is on every page load is not an interruption, so it is a polite status
    // rather than the primitive's default alert.
    <Alert
      role="status"
      className={cn(COLOR_CLASSES[color], "[&>svg]:text-current", className)}
    >
      {icon === "info" && <InfoIcon aria-hidden="true" className="size-4" />}
      {icon === "warning" && <TriangleAlertIcon aria-hidden="true" className="size-4" />}
      <AlertDescription className="[overflow-wrap:anywhere] whitespace-pre-line">
        {message}
      </AlertDescription>
    </Alert>
  );
}
