import type { ZxcvbnFactory as ZxcvbnFactoryType } from "@zxcvbn-ts/core";

// @zxcvbn-ts/core + its English dictionaries (language-common/language-en) are ~1.15MB of the
// production bundle on their own (measured: 2,355.85kB -> 1,200.55kB with this split out) — pure
// word-list/adjacency-graph data, not something that shrinks. They're only ever needed by
// PasswordStrengthMeter, itself only ever rendered on the New/Edit User password field, so
// dynamic-importing here keeps that weight off every other screen (including login, which never
// touches this at all) instead of shipping it in the main chunk unconditionally.
type Zxcvbn = InstanceType<typeof ZxcvbnFactoryType>;
let zxcvbnPromise: Promise<Zxcvbn> | null = null;

function loadZxcvbn(): Promise<Zxcvbn> {
  if (!zxcvbnPromise) {
    zxcvbnPromise = Promise.all([
      import("@zxcvbn-ts/core"),
      import("@zxcvbn-ts/language-common"),
      import("@zxcvbn-ts/language-en"),
    ]).then(([{ ZxcvbnFactory }, zxcvbnCommonPackage, zxcvbnEnPackage]) => {
      // @zxcvbn-ts/core is an actively-maintained fork of the original zxcvbn
      // (which is no longer maintained) — same scoring algorithm and dictionary
      // format, so this is a drop-in choice, not a behavior change.
      return new ZxcvbnFactory({
        translations: zxcvbnEnPackage.translations,
        graphs: zxcvbnCommonPackage.adjacencyGraphs,
        dictionary: {
          ...zxcvbnCommonPackage.dictionary,
          ...zxcvbnEnPackage.dictionary,
        },
      });
    });
  }
  return zxcvbnPromise;
}

// Called eagerly on mount by PasswordStrengthMeter (before the user necessarily types anything)
// so the download is already in flight by the time a score is actually needed.
export function preloadZxcvbn(): void {
  void loadZxcvbn();
}

export async function getPasswordScore(password: string): Promise<0 | 1 | 2 | 3 | 4> {
  if (!password) return 0;
  const zxcvbn = await loadZxcvbn();
  return zxcvbn.check(password).score;
}

// Single source of truth for score -> display label — raw scores are never shown
// alone.
export const PASSWORD_SCORE_LABELS: Record<0 | 1 | 2 | 3 | 4, string> = {
  0: "Very Weak",
  1: "Weak",
  2: "Fair",
  3: "Good",
  4: "Strong",
};
