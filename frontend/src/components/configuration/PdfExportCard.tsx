import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { PdfExportCardView } from "@/components/configuration/PdfExportCardView";
import {
  displayedHeight,
  usePdfExportSettings,
  type SaveResult,
} from "@/hooks/usePdfExportSettings";

export function PdfExportCard() {
  const { t } = useTranslation(["configuration"]);
  const { state, retry, setExportLogo, dragHeight, commitHeight } = usePdfExportSettings();

  // A rejection carries the server's reason; a failed request says nothing about the
  // value, so it gets a message of its own.
  const report = (result: SaveResult | null) => {
    if (result === null) return;
    if (result.ok) {
      toast.success(t("PDF export settings saved"));
    } else if (result.rejected) {
      toast.error(result.message);
    } else {
      toast.error(t("The setting didn't save. Check your connection and try again."));
    }
  };

  return (
    <PdfExportCardView
      loading={state.load === "loading"}
      loadFailed={state.load === "failed"}
      exportLogo={state.saved?.export_logo ?? null}
      heightMm={displayedHeight(state)}
      saving={state.saving}
      onExportLogoChange={(checked) => void setExportLogo(checked).then(report)}
      onHeightChange={dragHeight}
      onHeightCommit={(value) => void commitHeight(value).then(report)}
      onRetry={retry}
    />
  );
}
