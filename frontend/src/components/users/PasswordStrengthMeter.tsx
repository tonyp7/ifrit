import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { getPasswordScore, PASSWORD_SCORE_LABELS, preloadZxcvbn } from "@/lib/passwordStrength";

const BADGE_VARIANT_BY_SCORE = {
  0: "destructive",
  1: "destructive",
  2: "secondary",
  3: "default",
  4: "default",
} as const;

interface PasswordStrengthMeterProps {
  password: string;
}

// Live under any password-entry field, recomputed on every value change regardless
// of source (keystroke, paste, …) since it's driven by the controlled `password`
// prop, not an input event listener.
export function PasswordStrengthMeter({ password }: PasswordStrengthMeterProps) {
  const { t } = useTranslation(["user"]);
  const [score, setScore] = useState<0 | 1 | 2 | 3 | 4>(0);

  // Kick off zxcvbn's (dynamically-imported, ~1.15MB) download as soon as this field is on
  // screen, rather than waiting for the first keystroke: see passwordStrength.ts for why it's
  // lazy at all.
  useEffect(() => {
    preloadZxcvbn();
  }, []);

  useEffect(() => {
    let cancelled = false;
    void getPasswordScore(password).then((result) => {
      if (!cancelled) setScore(result);
    });
    return () => {
      cancelled = true;
    };
  }, [password]);

  return (
    <div className="flex flex-col gap-1.5">
      <Progress value={(score / 4) * 100} className="h-2" />
      <Badge variant={BADGE_VARIANT_BY_SCORE[score]} className="w-fit">
        {t("zxcvbn score: {{score}}/4", { score })} · {t(PASSWORD_SCORE_LABELS[score])}
      </Badge>
    </div>
  );
}
