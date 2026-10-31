import { useTranslation } from "react-i18next";

import { InformationBannerCardView } from "@/components/configuration/InformationBannerCardView";
import { reportSettingSave } from "@/components/configuration/settingToast";
import {
  useInformationBannerContext,
  refreshAfterSave,
} from "@/hooks/informationBannerContext";
import { isDirty, useInformationBannerSettings } from "@/hooks/useInformationBannerSettings";

export function InformationBannerCard() {
  const { t } = useTranslation(["configuration"]);
  const { state, retry, edit, setSwitch, saveDraft } = useInformationBannerSettings();
  // The strip across the signed-in pages is read again after a save the server accepted, so the
  // administrator, who is looking at that very page, sees the change take effect.
  const { refresh } = useInformationBannerContext();

  const networkMessage = t("The setting didn't save. Check your connection and try again.");

  return (
    <InformationBannerCardView
      loading={state.load === "loading"}
      loadFailed={state.load === "failed"}
      showOnLogin={state.saved?.show_on_login ?? null}
      showSiteWide={state.saved?.show_site_wide ?? null}
      draft={state.draft}
      dirty={isDirty(state)}
      saving={state.saving}
      onShowOnLoginChange={(checked) =>
        void setSwitch("show_on_login", checked).then((result) => {
          reportSettingSave(result, t("Information banner settings saved"), networkMessage);
          refreshAfterSave(result, refresh);
        })
      }
      onShowSiteWideChange={(checked) =>
        void setSwitch("show_site_wide", checked).then((result) => {
          reportSettingSave(result, t("Information banner settings saved"), networkMessage);
          refreshAfterSave(result, refresh);
        })
      }
      onDraftChange={edit}
      onSave={() =>
        void saveDraft().then((result) => {
          reportSettingSave(result, t("Information banner saved"), networkMessage);
          refreshAfterSave(result, refresh);
        })
      }
      onRetry={retry}
    />
  );
}
