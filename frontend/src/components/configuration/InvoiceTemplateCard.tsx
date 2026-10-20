import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import {
  downloadTemplate,
  getInvoiceTemplate,
  previewTemplate,
  resetTemplate,
  templateRejection,
  uploadTemplate,
} from "@/api/invoiceTemplate";
import {
  InvoiceTemplateCardView,
  type TemplateReview,
} from "@/components/configuration/InvoiceTemplateCardView";
import { downloadBlob } from "@/lib/download";
import type { InvoiceTemplateInfo } from "@/types/invoiceTemplate";

export function InvoiceTemplateCard() {
  const { t } = useTranslation(["configuration"]);
  const [info, setInfo] = useState<InvoiceTemplateInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [review, setReview] = useState<TemplateReview | null>(null);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [downloading, setDownloading] = useState(false);
  // The file being reviewed: what is confirmed is exactly what was previewed.
  const chosen = useRef<File | null>(null);

  useEffect(() => {
    let cancelled = false;
    getInvoiceTemplate()
      .then((current) => {
        if (!cancelled) setInfo(current);
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The object URL of a preview is released when the review goes away.
  useEffect(() => {
    if (review?.status !== "ready") return;
    const url = review.pdfUrl;
    return () => URL.revokeObjectURL(url);
  }, [review]);

  const choose = useCallback(
    async (file: File) => {
      chosen.current = file;
      setReview({ fileName: file.name, status: "checking" });
      try {
        const { blob, warnings } = await previewTemplate(file);
        setReview({
          fileName: file.name,
          status: "ready",
          pdfUrl: URL.createObjectURL(blob),
          warnings,
        });
      } catch (failure) {
        const rejection = templateRejection(failure);
        if (rejection) {
          setReview({ fileName: file.name, status: "rejected", ...rejection });
        } else {
          setReview({
            fileName: file.name,
            status: "failed",
            message:
              failure instanceof ApiError
                ? failure.message
                : t("The template could not be checked. Try again."),
          });
        }
      }
    },
    [t],
  );

  const confirm = useCallback(async () => {
    const file = chosen.current;
    if (!file) return;
    setSaving(true);
    try {
      const saved = await uploadTemplate(file);
      setInfo(saved);
      setReview(null);
      chosen.current = null;
      toast.success(t("Invoice template updated"));
    } catch (failure) {
      const rejection = templateRejection(failure);
      setReview(
        rejection
          ? { fileName: file.name, status: "rejected", ...rejection }
          : {
              fileName: file.name,
              status: "failed",
              message:
                failure instanceof ApiError
                  ? failure.message
                  : t("The template could not be saved. Try again."),
            },
      );
    } finally {
      setSaving(false);
    }
  }, [t]);

  const reset = useCallback(async () => {
    setResetting(true);
    try {
      await resetTemplate();
      setInfo(await getInvoiceTemplate());
      toast.success(t("The default invoice template is in use"));
    } catch (failure) {
      toast.error(
        failure instanceof ApiError ? failure.message : t("Couldn't reset the template."),
      );
    } finally {
      setResetting(false);
    }
  }, [t]);

  const download = useCallback(async () => {
    setDownloading(true);
    try {
      const { blob, filename } = await downloadTemplate();
      downloadBlob(blob, filename ?? "invoice-template.odt");
    } catch (failure) {
      toast.error(
        failure instanceof ApiError ? failure.message : t("Couldn't download the template."),
      );
    } finally {
      setDownloading(false);
    }
  }, [t]);

  return (
    <InvoiceTemplateCardView
      info={info}
      loading={loading}
      loadFailed={loadFailed}
      review={review}
      saving={saving}
      resetting={resetting}
      downloading={downloading}
      onChooseFile={(file) => void choose(file)}
      onConfirm={() => void confirm()}
      onCancel={() => {
        setReview(null);
        chosen.current = null;
      }}
      onReset={() => void reset()}
      onDownload={() => void download()}
    />
  );
}
