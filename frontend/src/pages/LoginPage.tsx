import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation(["auth"]);
  const [formError, setFormError] = useState<string | null>(null);

  // Built inside the component (not at module scope) so the validation messages can
  // go through t() — see docs/architecture/frontend.md#internationalization-i18n.
  const loginSchema = useMemo(
    () =>
      z.object({
        email: z.string().min(1, t("Email is required")),
        password: z.string().min(1, t("Password is required")),
      }),
    [t],
  );
  type LoginFormValues = z.infer<typeof loginSchema>;

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(values: LoginFormValues) {
    setFormError(null);
    try {
      await login(values.email, values.password);
      navigate("/", { replace: true });
    } catch (err) {
      // Generic message: don't reveal whether the email exists (see auth.md).
      setFormError(
        err instanceof ApiError ? err.message : t("Something went wrong. Please try again."),
      );
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{t("Sign in to Ifrit")}</CardTitle>
          <CardDescription>{t("Enter your email and password to continue.")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <FieldGroup>
              <Field data-invalid={!!errors.email}>
                <FieldLabel htmlFor="email">{t("Email")}</FieldLabel>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  aria-invalid={!!errors.email}
                  {...register("email")}
                />
                <FieldError errors={errors.email && [errors.email]} />
              </Field>
              <Field data-invalid={!!errors.password}>
                <FieldLabel htmlFor="password">{t("Password")}</FieldLabel>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  aria-invalid={!!errors.password}
                  {...register("password")}
                />
                <FieldError errors={errors.password && [errors.password]} />
              </Field>
              {formError && <p className="text-sm text-destructive">{formError}</p>}
              <Button type="submit" disabled={isSubmitting} className="mt-2">
                {isSubmitting ? t("Signing in…") : t("Sign in")}
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
