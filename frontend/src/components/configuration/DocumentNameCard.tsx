import { useTranslation } from "react-i18next";

import { getInvoicingSettings, patchInvoicingSettings } from "@/api/settings";
import { DocumentNameCardView } from "@/components/configuration/DocumentNameCardView";
import { reportSettingSave } from "@/components/configuration/settingToast";
import { useSettingField } from "@/hooks/useSettingField";

// Module-level, so the hook's load effect sees the same functions on every render.
const read = () => getInvoicingSettings().then((group) => group.document_name);
const write = (name: string) =>
  patchInvoicingSettings({ document_name: name }).then((group) => group.document_name);

export function DocumentNameCard() {
  const { t } = useTranslation(["configuration"]);
  const { state, retry, commit } = useSettingField(read, write);

  return (
    <DocumentNameCardView
      loading={state.load === "loading"}
      loadFailed={state.load === "failed"}
      name={state.saved}
      saving={state.saving}
      onCommit={(name) =>
        void commit(name).then((result) =>
          reportSettingSave(
            result,
            t("Document name saved"),
            t("The setting didn't save. Check your connection and try again."),
          ),
        )
      }
      onRetry={retry}
    />
  );
}
