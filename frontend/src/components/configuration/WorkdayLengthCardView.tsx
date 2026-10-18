import {
  useEffect,
  useId,
  useRef,
  useState,
  type FocusEvent,
  type KeyboardEvent,
} from "react";
import { useTranslation } from "react-i18next";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  joinDuration,
  parsePart,
  PART_MAX,
  splitDuration,
  type DurationParts,
} from "@/lib/workdayDuration";

export interface WorkdayLengthCardViewProps {
  /** True until the saved setting has been read, whatever the outcome. */
  loading: boolean;
  loadFailed: boolean;
  /** Null until the saved setting is known, so a default is never shown as saved. */
  seconds: number | null;
  saving: boolean;
  /** Fires once per committed edit with the length that will be saved. */
  onCommit: (seconds: number) => void;
  onRetry: () => void;
}

type Drafts = Record<keyof DurationParts, string>;

const PARTS: { key: keyof DurationParts; label: string }[] = [
  { key: "hours", label: "Hours" },
  { key: "minutes", label: "Minutes" },
  { key: "seconds", label: "Seconds" },
];

function draftsFor(seconds: number | null): Drafts {
  if (seconds === null) return { hours: "", minutes: "", seconds: "" };
  const parts = splitDuration(seconds);
  return {
    hours: String(parts.hours),
    minutes: String(parts.minutes),
    seconds: String(parts.seconds),
  };
}

export function WorkdayLengthCardView({
  loading,
  loadFailed,
  seconds,
  saving,
  onCommit,
  onRetry,
}: WorkdayLengthCardViewProps) {
  const { t } = useTranslation(["configuration"]);
  const legendId = useId();
  const idPrefix = useId();
  const unavailable = loading || loadFailed;

  const [drafts, setDrafts] = useState<Drafts>(() => draftsFor(seconds));
  // Show the saved value again whenever it changes or a save ends: after a success that is
  // the server's value, after a failure it puts back the last saved one.
  const [shown, setShown] = useState({ seconds, saving });
  if (shown.seconds !== seconds || shown.saving !== saving) {
    setShown({ seconds, saving });
    if (!saving) setDrafts(draftsFor(seconds));
  }

  // The fields are disabled while saving, which drops the keyboard focus; an Enter commit
  // puts it back on the field it came from once the save ends.
  const focusedBeforeSave = useRef<HTMLElement | null>(null);
  const wasSaving = useRef(false);
  useEffect(() => {
    if (wasSaving.current && !saving) focusedBeforeSave.current?.focus();
    wasSaving.current = saving;
  }, [saving]);

  const commit = () => {
    const total = joinDuration({
      hours: parsePart(drafts.hours, PART_MAX.hours),
      minutes: parsePart(drafts.minutes, PART_MAX.minutes),
      seconds: parsePart(drafts.seconds, PART_MAX.seconds),
    });
    // The fields show the value that will be saved, bounds applied.
    setDrafts(draftsFor(total));
    onCommit(total);
  };

  // Moving between Hours, Minutes and Seconds is not a commit; leaving the group is.
  const onBlur = (event: FocusEvent<HTMLFieldSetElement>) => {
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) return;
    commit();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLFieldSetElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    focusedBeforeSave.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    commit();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-medium">{t("Standard Workday Length")}</CardTitle>
        <CardDescription>
          {t("Converts logged hours into days on invoices, for service lines billed in days.")}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <fieldset
          aria-labelledby={legendId}
          className="flex flex-wrap items-end gap-3"
          onBlur={onBlur}
          onKeyDown={onKeyDown}
        >
          <legend id={legendId} className="sr-only">
            {t("Standard Workday Length")}
          </legend>
          {PARTS.map(({ key, label }) => (
            <div key={key} className="flex w-20 flex-col gap-1.5">
              <Label htmlFor={`${idPrefix}-${key}`}>{t(label)}</Label>
              <Input
                id={`${idPrefix}-${key}`}
                type="number"
                inputMode="numeric"
                min={0}
                max={PART_MAX[key]}
                step={1}
                className="tabular-nums pointer-coarse:h-11"
                value={drafts[key]}
                disabled={unavailable || saving}
                onChange={(event) =>
                  setDrafts((current) => ({ ...current, [key]: event.target.value }))
                }
              />
            </div>
          ))}
        </fieldset>

        {loadFailed && (
          <Alert variant="destructive">
            <AlertDescription className="flex flex-col items-start gap-2">
              {t("Couldn't load the workday length.")}
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
