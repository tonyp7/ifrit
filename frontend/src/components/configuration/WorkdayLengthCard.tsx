import { useTranslation } from "react-i18next";

import { getGeneralSettings, patchGeneralSettings } from "@/api/settings";
import { reportSettingSave } from "@/components/configuration/settingToast";
import { WorkdayLengthCardView } from "@/components/configuration/WorkdayLengthCardView";
import { useSettingField } from "@/hooks/useSettingField";

// Module-level, so the hook's load effect sees the same functions on every render.
const read = () => getGeneralSettings().then((group) => group.standard_workday_seconds);
const write = (seconds: number) =>
  patchGeneralSettings({ standard_workday_seconds: seconds }).then(
    (group) => group.standard_workday_seconds,
  );

export function WorkdayLengthCard() {
  const { t } = useTranslation(["configuration"]);
  const { state, retry, commit } = useSettingField(read, write);

  return (
    <WorkdayLengthCardView
      loading={state.load === "loading"}
      loadFailed={state.load === "failed"}
      seconds={state.saved}
      saving={state.saving}
      onCommit={(seconds) =>
        void commit(seconds).then((result) =>
          reportSettingSave(
            result,
            t("Workday length saved"),
            t("The setting didn't save. Check your connection and try again."),
          ),
        )
      }
      onRetry={retry}
    />
  );
}
