import { zodResolver } from "@hookform/resolvers/zod";
import { TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { ApiError } from "@/api/client";
import { createUser, getUser, updateUser } from "@/api/users";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { PasswordStrengthMeter } from "@/components/users/PasswordStrengthMeter";
import { useAuth } from "@/hooks/useAuth";
import { ROLE_LABELS, type Role, type User } from "@/types/user";

const ALL_ROLES: Role[] = ["administrator", "project_admin", "project_manager", "consultant"];

const BLANK_VALUES = {
  full_name: "",
  name_id: "",
  is_sso: false,
  roles: ["consultant"] as Role[],
  password: "",
};

interface DuplicateFromState {
  duplicateFrom?: { roles: Role[]; is_sso: boolean };
}

export function UserFormPage() {
  const { userId: routeUserId } = useParams<{ userId: string }>();
  const isNew = !routeUserId;
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation(["user", "common"]);
  const { user: currentUser } = useAuth();

  const [user, setUser] = useState<User | null>(null);
  const [originalIsSso, setOriginalIsSso] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const duplicateFrom = (location.state as DuplicateFromState | null)?.duplicateFrom;
  const initialValues = duplicateFrom
    ? { ...BLANK_VALUES, roles: duplicateFrom.roles, is_sso: duplicateFrom.is_sso }
    : BLANK_VALUES;

  const isEditingSelf = !isNew && routeUserId === currentUser?.id;

  // The resolver reads `is_sso` from whatever values it's given at validation time
  // (submit), not from `watch()` on this same form — a schema built from live
  // watched values would be circular (useForm needs the resolver, the resolver
  // would need useForm's watch). `isNew`/`originalIsSso` are plain state, not form
  // values, so this has no such cycle.
  const schema = useMemo(
    () =>
      z
        .object({
          full_name: z.string().min(1, t("Full name is required")),
          name_id: z.string().min(1, t("Login identity is required")),
          is_sso: z.boolean(),
          roles: z
            .array(z.enum(["administrator", "project_admin", "project_manager", "consultant"]))
            .min(1, t("At least one role is required")),
          password: z.string(),
        })
        .superRefine((values, ctx) => {
          const passwordRequired = isNew ? !values.is_sso : originalIsSso && !values.is_sso;
          if (!passwordRequired) return;
          if (values.password.length < 12) {
            ctx.addIssue({
              code: z.ZodIssueCode.custom,
              path: ["password"],
              message: t("Password must be at least 12 characters"),
            });
          } else if (values.password.length > 255) {
            ctx.addIssue({
              code: z.ZodIssueCode.custom,
              path: ["password"],
              message: t("Password must be at most 255 characters"),
            });
          }
        }),
    [t, isNew, originalIsSso],
  );
  type FormValues = z.infer<typeof schema>;

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: initialValues });

  const watchedIsSso = watch("is_sso");
  const watchedRoles = watch("roles");
  const watchedPassword = watch("password");

  // New + local: always needs a password. Edit + switching an SSO user back to
  // local: also needs one (their old password is long gone). Otherwise hidden —
  // an already-local user's password changes via the Reset Password row action,
  // not this form. See docs/requirements/user.md#user-form-create--edit--duplicate.
  const showPasswordField = isNew ? !watchedIsSso : originalIsSso && !watchedIsSso;
  // Only local -> SSO (not the reverse) needs the destructive warning.
  const showSsoWarning = !isNew && !originalIsSso && watchedIsSso;

  useEffect(() => {
    if (routeUserId) {
      getUser(routeUserId)
        .then((detail) => {
          setUser(detail);
          setOriginalIsSso(detail.is_sso);
          reset({
            full_name: detail.full_name,
            name_id: detail.name_id,
            is_sso: detail.is_sso,
            roles: detail.roles,
            password: "",
          });
        })
        .catch((err: unknown) => {
          setLoadError(err instanceof ApiError ? err.message : t("Failed to load user."));
        });
    } else {
      setUser(null);
      setOriginalIsSso(false);
      reset(initialValues);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeUserId]);

  function toggleRole(role: Role, checked: boolean) {
    const current = new Set(watchedRoles);
    if (checked) current.add(role);
    else current.delete(role);
    setValue("roles", Array.from(current) as Role[], { shouldValidate: true });
  }

  function buildPayload(values: FormValues) {
    return {
      full_name: values.full_name,
      name_id: values.name_id,
      is_sso: values.is_sso,
      roles: values.roles,
      password: showPasswordField && values.password ? values.password : null,
    };
  }

  async function onSubmit(values: z.infer<typeof schema>) {
    setFormError(null);
    try {
      if (user) {
        const updated = await updateUser(user.id, buildPayload(values));
        setUser(updated);
        setOriginalIsSso(updated.is_sso);
      } else {
        const created = await createUser(buildPayload(values));
        navigate(`/configuration/users/${created.id}`, { replace: true });
      }
      toast.success(t("User saved."));
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : t("Failed to save user."));
    }
  }

  if (routeUserId && loadError) {
    return <p className="p-4 text-sm text-destructive">{loadError}</p>;
  }

  return (
    <div className="mx-auto max-w-3xl p-4">
      <Card>
        <CardHeader>
          <CardTitle>{isNew ? t("New User") : t("Edit User")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)}>
            <FieldGroup>
              <Field data-invalid={!!errors.full_name}>
                <FieldLabel htmlFor="full_name">{t("Full name")}</FieldLabel>
                <Input
                  id="full_name"
                  aria-invalid={!!errors.full_name}
                  {...register("full_name")}
                />
                <FieldError errors={errors.full_name && [errors.full_name]} />
              </Field>

              <Field data-invalid={!!errors.name_id}>
                <FieldLabel htmlFor="name_id">{t("Login identity")}</FieldLabel>
                <Input id="name_id" aria-invalid={!!errors.name_id} {...register("name_id")} />
                <FieldError errors={errors.name_id && [errors.name_id]} />
              </Field>

              <Field orientation="horizontal">
                <Switch
                  id="is_sso"
                  checked={watchedIsSso}
                  onCheckedChange={(checked) => setValue("is_sso", checked)}
                />
                <FieldLabel htmlFor="is_sso">{t("SSO User")}</FieldLabel>
              </Field>

              {showSsoWarning && (
                <Alert variant="destructive">
                  <TriangleAlert className="h-4 w-4" aria-hidden="true" />
                  <AlertTitle>{t("This will remove the user's password")}</AlertTitle>
                  <AlertDescription>
                    {t(
                      "Changing this user to SSO will remove this user's existing password. The user's current password will not be recoverable and will need to be re-initialized if it is switched back to a local user. Proceed with caution.",
                    )}
                  </AlertDescription>
                </Alert>
              )}

              {showPasswordField && (
                <Field data-invalid={!!errors.password}>
                  <FieldLabel htmlFor="password">{t("Initial password")}</FieldLabel>
                  <Input
                    id="password"
                    type="password"
                    aria-invalid={!!errors.password}
                    {...register("password")}
                  />
                  <FieldError errors={errors.password && [errors.password]} />
                  <PasswordStrengthMeter password={watchedPassword} />
                </Field>
              )}

              <FieldSet data-invalid={!!errors.roles}>
                <FieldLegend variant="label">{t("Roles")}</FieldLegend>
                {/* [container-type:normal] disables FieldGroup's default `@container` query
                    containment: we never use the "responsive" Field orientation that needs it,
                    and leaving it on triggers a real Chromium bug where this nested FieldGroup
                    (a container-query element inside another one) collapses to 0 height on the
                    next re-render — reproduced live by unchecking a role checkbox. */}
                <FieldGroup className="gap-3 [container-type:normal]">
                  {ALL_ROLES.map((role) => (
                    <Field orientation="horizontal" key={role}>
                      <Checkbox
                        id={`role-${role}`}
                        checked={watchedRoles.includes(role)}
                        disabled={role === "administrator" && isEditingSelf}
                        onCheckedChange={(checked) => toggleRole(role, checked === true)}
                      />
                      <FieldLabel htmlFor={`role-${role}`} className="font-normal">
                        {t(ROLE_LABELS[role])}
                      </FieldLabel>
                    </Field>
                  ))}
                </FieldGroup>
                {isEditingSelf && (
                  <FieldDescription>
                    {t("You can't remove your own administrator access.")}
                  </FieldDescription>
                )}
                <FieldError errors={errors.roles && [errors.roles]} />
              </FieldSet>

              {formError && <p className="text-sm text-destructive">{formError}</p>}

              <Separator />

              <div className="flex justify-between">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => navigate("/configuration/users")}
                >
                  {t("Close", { ns: "common" })}
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {t("Save", { ns: "common" })}
                </Button>
              </div>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
