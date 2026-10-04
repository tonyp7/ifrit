import { useEffect, useId, useRef } from "react";
import { useTranslation } from "react-i18next";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { LOGO_HEIGHT_MAX_MM, LOGO_HEIGHT_MIN_MM } from "@/types/settings";

export interface PdfExportCardViewProps {
  /** True until the saved settings have been read, whatever the outcome. */
  loading: boolean;
  loadFailed: boolean;
  /** Null until the saved settings are known, so a default is never shown as saved. */
  exportLogo: boolean | null;
  /** The thumb's position while it moves, the saved height otherwise. */
  heightMm: number | null;
  saving: boolean;
  onExportLogoChange: (checked: boolean) => void;
  /** Fires continuously while the thumb moves; must not save. */
  onHeightChange: (value: number) => void;
  /** Fires once the adjustment is finished (release, or a settled key press). */
  onHeightCommit: (value: number) => void;
  onRetry: () => void;
}

export function PdfExportCardView({
  loading,
  loadFailed,
  exportLogo,
  heightMm,
  saving,
  onExportLogoChange,
  onHeightChange,
  onHeightCommit,
  onRetry,
}: PdfExportCardViewProps) {
  const { t } = useTranslation(["configuration"]);
  const switchId = useId();
  const heightLabelId = useId();
  const unavailable = loading || loadFailed;

  // A control is disabled while its save is in flight, and a disabled element loses the
  // keyboard focus. Remembering the focused element when a change is made and focusing it
  // again once the save ends lets a keyboard user keep adjusting without tabbing back.
  const focusedBeforeSave = useRef<HTMLElement | null>(null);
  const wasSaving = useRef(false);
  const rememberFocus = () => {
    focusedBeforeSave.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
  };
  useEffect(() => {
    if (wasSaving.current && !saving) focusedBeforeSave.current?.focus();
    wasSaving.current = saving;
  }, [saving]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-medium">{t("PDF Report Export")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div className="flex items-center justify-between gap-4">
          <Label htmlFor={switchId}>{t("Insert organization logo in exported PDF")}</Label>
          <Switch
            id={switchId}
            checked={exportLogo ?? false}
            disabled={unavailable || saving}
            onCheckedChange={(checked) => {
              rememberFocus();
              onExportLogoChange(checked);
            }}
          />
        </div>

        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-4">
            <Label id={heightLabelId}>{t("Logo height, in mm")}</Label>
            <span
              className="text-muted-foreground text-sm tabular-nums"
              data-testid="logo-height-value"
            >
              {heightMm ?? ""}
            </span>
          </div>
          {/* Stays visible, with its value, while the logo is off: the stored height is
              kept for when it is switched back on, it just cannot be changed meanwhile. */}
          <Slider
            aria-labelledby={heightLabelId}
            // Radix marks a disabled slider with data-disabled, which the generated styles
            // don't dim, so without this it would look usable while the logo is off.
            className="data-[disabled]:opacity-50"
            min={LOGO_HEIGHT_MIN_MM}
            max={LOGO_HEIGHT_MAX_MM}
            step={1}
            value={[heightMm ?? LOGO_HEIGHT_MIN_MM]}
            disabled={unavailable || saving || exportLogo !== true}
            onValueChange={([value]) => onHeightChange(value)}
            onValueCommit={([value]) => {
              rememberFocus();
              onHeightCommit(value);
            }}
          />
        </div>

        {loadFailed && (
          <Alert variant="destructive">
            <AlertDescription className="flex flex-col items-start gap-2">
              {t("Couldn't load the PDF export settings.")}
              <Button type="button" size="sm" variant="outline" onClick={onRetry}>
                {t("Try again")}
              </Button>
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
