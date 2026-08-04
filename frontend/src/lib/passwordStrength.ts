import { ZxcvbnFactory } from "@zxcvbn-ts/core";
import * as zxcvbnCommonPackage from "@zxcvbn-ts/language-common";
import * as zxcvbnEnPackage from "@zxcvbn-ts/language-en";

// Built once at module load, not per-render — see docs/requirements/user.md#password-policy
// for why @zxcvbn-ts/core (not the unmaintained original zxcvbn) drives the live
// strength meter.
const zxcvbn = new ZxcvbnFactory({
  translations: zxcvbnEnPackage.translations,
  graphs: zxcvbnCommonPackage.adjacencyGraphs,
  dictionary: {
    ...zxcvbnCommonPackage.dictionary,
    ...zxcvbnEnPackage.dictionary,
  },
});

export function getPasswordScore(password: string): 0 | 1 | 2 | 3 | 4 {
  if (!password) return 0;
  return zxcvbn.check(password).score;
}

// Single source of truth for score -> display label, per
// docs/requirements/user.md#password-policy — raw scores are never shown alone.
export const PASSWORD_SCORE_LABELS: Record<0 | 1 | 2 | 3 | 4, string> = {
  0: "Very Weak",
  1: "Weak",
  2: "Fair",
  3: "Good",
  4: "Strong",
};
