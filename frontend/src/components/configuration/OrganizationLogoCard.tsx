import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { deleteOrgLogo, getOrgLogo, uploadOrgLogo } from "@/api/settings";
import { OrganizationLogoCardView } from "@/components/configuration/OrganizationLogoCardView";
import { useFileUpload } from "@/hooks/useFileUpload";
import type { StoredFileInfo } from "@/types/file";

export function OrganizationLogoCard() {
  const { t } = useTranslation(["configuration"]);
  const [logo, setLogo] = useState<StoredFileInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [removing, setRemoving] = useState(false);
  const lastFile = useRef<File | null>(null);
  const { status, progress, error, upload } = useFileUpload(uploadOrgLogo);

  useEffect(() => {
    let cancelled = false;
    getOrgLogo()
      .then((current) => {
        if (!cancelled) setLogo(current);
      })
      .catch((failure: unknown) => {
        // 404 just means no logo has been uploaded yet.
        if (cancelled || (failure instanceof ApiError && failure.status === 404)) return;
        setLoadFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const startUpload = useCallback(
    async (file: File) => {
      lastFile.current = file;
      const result = await upload(file);
      if (result) {
        setLogo(result);
        toast.success(t("Logo updated"));
      }
    },
    [upload, t],
  );

  // The reason for a rejection is shown in the card; the toast repeats it where it
  // can't be missed. A network failure keeps the card's retry affordance instead.
  useEffect(() => {
    if (status === "rejected" && error) toast.error(error);
  }, [status, error]);

  const remove = useCallback(async () => {
    setRemoving(true);
    try {
      await deleteOrgLogo();
      setLogo(null);
      toast.success(t("Logo removed"));
    } catch (failure) {
      toast.error(failure instanceof Error ? failure.message : t("Upload failed"));
    } finally {
      setRemoving(false);
    }
  }, [t]);

  return (
    <OrganizationLogoCardView
      logo={logo}
      loading={loading}
      loadFailed={loadFailed}
      upload={{ status, progress, error }}
      removing={removing}
      onBrowse={(file) => void startUpload(file)}
      onRetry={() => {
        if (lastFile.current) void startUpload(lastFile.current);
      }}
      onRemove={() => void remove()}
    />
  );
}
