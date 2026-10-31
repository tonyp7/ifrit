import { InfoIcon, TriangleAlertIcon } from "lucide-react";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import { InformationBanner } from "@/components/InformationBanner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { BannerDraft } from "@/hooks/useInformationBannerSettings";
import {
  BANNER_MESSAGE_MAX_LENGTH,
  type BannerColor,
  type BannerIcon,
} from "@/types/settings";

export interface InformationBannerCardViewProps {
  /** True until the saved settings have been read, whatever the outcome. */
  loading: boolean;
  loadFailed: boolean;
  /** Null until the saved settings are known, so a default is never shown as saved. */
  showOnLogin: boolean | null;
  showSiteWide: boolean | null;
  draft: BannerDraft | null;
  /** The draft differs from what is stored. */
  dirty: boolean;
  saving: boolean;
  onShowOnLoginChange: (checked: boolean) => void;
  onShowSiteWideChange: (checked: boolean) => void;
  onDraftChange: (change: Partial<BannerDraft>) => void;
  onSave: () => void;
  onRetry: () => void;
}

const ICON_OPTIONS: BannerIcon[] = ["none", "info", "warning"];
const COLOR_OPTIONS: BannerColor[] = ["neutral", "blue", "yellow", "red"];

// A small round swatch beside each color's name, so the choice is never color alone.
const SWATCH_CLASSES: Record<BannerColor, string> = {
  neutral: "bg-muted border-border",
  blue: "bg-blue-200 border-blue-400",
  yellow: "bg-yellow-200 border-yellow-500",
  red: "bg-red-200 border-red-400",
};

// Touch targets of at least 44 px, wrapping onto further lines on a narrow screen.
const CHOICE_GROUP_CLASSES = "flex-wrap justify-start";
const CHOICE_ITEM_CLASSES = "min-h-11 gap-2 px-3";

export function InformationBannerCardView({
  loading,
  loadFailed,
  showOnLogin,
  showSiteWide,
  draft,
  dirty,
  saving,
  onShowOnLoginChange,
  onShowSiteWideChange,
  onDraftChange,
  onSave,
  onRetry,
}: InformationBannerCardViewProps) {
  const { t } = useTranslation(["configuration"]);
  const loginSwitchId = useId();
  const siteWideSwitchId = useId();
  const messageId = useId();
  const noteId = useId();
  const unavailable = loading || loadFailed;
  const locked = unavailable || saving;
  const message = draft?.message ?? "";
  const nothingOn = showOnLogin !== true && showSiteWide !== true;

  const iconLabels: Record<BannerIcon, string> = {
    none: t("None"),
    info: t("Info"),
    warning: t("Warning"),
  };
  const colorLabels: Record<BannerColor, string> = {
    neutral: t("Neutral"),
    blue: t("Blue"),
    yellow: t("Yellow"),
    red: t("Red"),
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-medium">{t("Information Banner")}</CardTitle>
        <CardDescription>
          {t(
            "Show a message to everyone, on the sign-in page and across the top of every page.",
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        {/* Switches save at once and never touch the draft below. They stay usable whatever
            the message says, and the message stays editable whatever they say. */}
        <Field orientation="horizontal">
          <Switch
            id={loginSwitchId}
            checked={showOnLogin ?? false}
            disabled={locked}
            onCheckedChange={onShowOnLoginChange}
          />
          <FieldLabel htmlFor={loginSwitchId}>
            {t("Display information banner on login page")}
          </FieldLabel>
        </Field>
        <Field orientation="horizontal">
          <Switch
            id={siteWideSwitchId}
            checked={showSiteWide ?? false}
            disabled={locked}
            onCheckedChange={onShowSiteWideChange}
          />
          <FieldLabel htmlFor={siteWideSwitchId}>
            {t("Display information banner site wide on page top")}
          </FieldLabel>
        </Field>

        <Field>
          <FieldLabel htmlFor={messageId}>{t("Message")}</FieldLabel>
          <Textarea
            id={messageId}
            aria-describedby={noteId}
            rows={3}
            maxLength={BANNER_MESSAGE_MAX_LENGTH}
            value={message}
            disabled={locked}
            onChange={(event) => onDraftChange({ message: event.target.value })}
          />
          <div className="flex items-start justify-between gap-4">
            <FieldDescription id={noteId}>
              {t("Visible to everyone, including people who are not signed in.")}
            </FieldDescription>
            <span className="text-muted-foreground shrink-0 text-sm tabular-nums">
              {message.length} / {BANNER_MESSAGE_MAX_LENGTH}
            </span>
          </div>
        </Field>

        <div className="flex flex-col gap-2">
          <Label>{t("Icon")}</Label>
          <ToggleGroup
            type="single"
            variant="outline"
            aria-label={t("Icon")}
            className={CHOICE_GROUP_CLASSES}
            value={draft?.icon ?? ""}
            disabled={locked}
            // Pressing the selected item again reports an empty value; one option always
            // stays chosen, so it is ignored.
            onValueChange={(value) => value && onDraftChange({ icon: value as BannerIcon })}
          >
            {ICON_OPTIONS.map((icon) => (
              <ToggleGroupItem key={icon} value={icon} className={CHOICE_ITEM_CLASSES}>
                {icon === "info" && <InfoIcon aria-hidden="true" className="size-4" />}
                {icon === "warning" && (
                  <TriangleAlertIcon aria-hidden="true" className="size-4" />
                )}
                {iconLabels[icon]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>

        <div className="flex flex-col gap-2">
          <Label>{t("Color")}</Label>
          <ToggleGroup
            type="single"
            variant="outline"
            aria-label={t("Color")}
            className={CHOICE_GROUP_CLASSES}
            value={draft?.color ?? ""}
            disabled={locked}
            onValueChange={(value) => value && onDraftChange({ color: value as BannerColor })}
          >
            {COLOR_OPTIONS.map((color) => (
              <ToggleGroupItem key={color} value={color} className={CHOICE_ITEM_CLASSES}>
                <span
                  aria-hidden="true"
                  className={`size-3 rounded-full border ${SWATCH_CLASSES[color]}`}
                />
                {colorLabels[color]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>

        {/* The preview shows the draft with the very component visitors get, whatever the
            switches say, so a prepared message can be reviewed before it goes live. */}
        <div className="flex flex-col gap-2">
          <Label>{t("Preview")}</Label>
          {draft && message.trim() !== "" ? (
            <InformationBanner message={message} icon={draft.icon} color={draft.color} />
          ) : (
            <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
              {t("Nothing will be shown.")}
            </p>
          )}
          {!unavailable && nothingOn && (
            <p className="text-muted-foreground text-sm">{t("Not shown anywhere yet.")}</p>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-3">
          {dirty && (
            <span className="text-muted-foreground text-sm">
              {t("You have unsaved changes.")}
            </span>
          )}
          <Button type="button" disabled={unavailable || saving || !dirty} onClick={onSave}>
            {saving && <Spinner />}
            {t("Save changes")}
          </Button>
        </div>

        {loadFailed && (
          <Alert variant="destructive">
            <AlertDescription className="flex flex-col items-start gap-2">
              {t("Couldn't load the information banner settings.")}
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
