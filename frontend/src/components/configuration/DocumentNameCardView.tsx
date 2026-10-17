import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
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
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { DOCUMENT_NAME_MAX_LENGTH } from "@/types/settings";

export interface DocumentNameCardViewProps {
  /** True until the saved setting has been read, whatever the outcome. */
  loading: boolean;
  loadFailed: boolean;
  /** Null until the saved setting is known, so a default is never shown as saved. */
  name: string | null;
  saving: boolean;
  /** Fires once per committed edit with the trimmed, non-empty name. */
  onCommit: (name: string) => void;
  onRetry: () => void;
}

export function DocumentNameCardView({
  loading,
  loadFailed,
  name,
  saving,
  onCommit,
  onRetry,
}: DocumentNameCardViewProps) {
  const { t } = useTranslation(["configuration"]);
  const inputId = useId();
  const unavailable = loading || loadFailed;

  const [draft, setDraft] = useState(name ?? "");
  const [required, setRequired] = useState(false);
  // Show the saved value again whenever it changes or a save ends: after a success that is
  // the server's value, after a failure it puts back the last saved one.
  const [shown, setShown] = useState({ name, saving });
  if (shown.name !== name || shown.saving !== saving) {
    setShown({ name, saving });
    if (!saving) setDraft(name ?? "");
  }

  // The field is disabled while saving, which drops the keyboard focus; an Enter commit
  // puts it back once the save ends.
  const inputRef = useRef<HTMLInputElement>(null);
  const refocus = useRef(false);
  const wasSaving = useRef(false);
  useEffect(() => {
    if (wasSaving.current && !saving && refocus.current) {
      inputRef.current?.focus();
      refocus.current = false;
    }
    wasSaving.current = saving;
  }, [saving]);

  const commit = () => {
    const trimmed = draft.trim();
    if (!trimmed) {
      setRequired(true);
      return;
    }
    setRequired(false);
    setDraft(trimmed);
    onCommit(trimmed);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    refocus.current = true;
    commit();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-medium">{t("Document Name")}</CardTitle>
        <CardDescription>
          {t(
            'The title invoices carry. Some jurisdictions require a title such as "Tax Invoice".',
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Field data-invalid={required} className="w-full max-w-sm">
          <FieldLabel htmlFor={inputId}>{t("Document name")}</FieldLabel>
          <Input
            id={inputId}
            ref={inputRef}
            aria-invalid={required}
            maxLength={DOCUMENT_NAME_MAX_LENGTH}
            className="pointer-coarse:h-11"
            value={draft}
            disabled={unavailable || saving}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={commit}
            onKeyDown={onKeyDown}
          />
          <FieldError
            errors={required ? [{ message: t("A document name is required") }] : undefined}
          />
        </Field>

        {loadFailed && (
          <Alert variant="destructive">
            <AlertDescription className="flex flex-col items-start gap-2">
              {t("Couldn't load the document name.")}
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
