import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { PasswordStrengthMeter } from "@/components/users/PasswordStrengthMeter";

interface ResetPasswordDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userName: string;
  onConfirm: (newPassword: string) => Promise<void>;
}

// Same 12-255-character/printable-character rule and live strength meter as the
// User Form's initial-password field.
export function ResetPasswordDialog({
  open,
  onOpenChange,
  userName,
  onConfirm,
}: ResetPasswordDialogProps) {
  const { t } = useTranslation(["user", "common"]);
  const [formError, setFormError] = useState<string | null>(null);

  const schema = useMemo(
    () =>
      z.object({
        new_password: z
          .string()
          .min(12, t("Password must be at least 12 characters"))
          .max(255, t("Password must be at most 255 characters")),
      }),
    [t],
  );
  type FormValues = z.infer<typeof schema>;

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { new_password: "" },
  });

  useEffect(() => {
    if (open) {
      setFormError(null);
      reset({ new_password: "" });
    }
  }, [open, reset]);

  const password = watch("new_password");

  async function onSubmit(values: FormValues) {
    setFormError(null);
    try {
      await onConfirm(values.new_password);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to reset password."));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("Reset password for {{name}}", { name: userName })}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="new_password">{t("New password")}</Label>
            <Input id="new_password" type="password" {...register("new_password")} />
            {errors.new_password && (
              <p className="text-sm text-destructive">{errors.new_password.message}</p>
            )}
            <PasswordStrengthMeter password={password} />
          </div>

          {formError && <p className="text-sm text-destructive">{formError}</p>}

          <DialogFooter>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Spinner />}
              {isSubmitting ? t("Saving…", { ns: "common" }) : t("Save", { ns: "common" })}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
