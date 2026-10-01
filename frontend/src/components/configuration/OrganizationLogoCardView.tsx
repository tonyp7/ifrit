import { ImageIcon, Upload } from "lucide-react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";

import { fileContentUrl } from "@/api/settings";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AspectRatio } from "@/components/ui/aspect-ratio";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import type { UploadStatus } from "@/hooks/useFileUpload";
import type { StoredFileInfo } from "@/types/file";

// What the file chooser offers. The server re-checks the real content, this only saves
// the user from picking something that is certain to be refused.
const ACCEPTED_TYPES = ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp";

export interface OrganizationLogoCardViewProps {
  logo: StoredFileInfo | null;
  /** True until the lookup of the current logo has finished, whatever its outcome. */
  loading: boolean;
  loadFailed: boolean;
  upload: { status: UploadStatus; progress: number; error: string | null };
  removing: boolean;
  onBrowse: (file: File) => void;
  onRetry: () => void;
  onRemove: () => void;
}

export function OrganizationLogoCardView({
  logo,
  loading,
  loadFailed,
  upload,
  removing,
  onBrowse,
  onRetry,
  onRemove,
}: OrganizationLogoCardViewProps) {
  const { t } = useTranslation(["configuration", "common"]);
  const inputRef = useRef<HTMLInputElement>(null);
  const uploading = upload.status === "uploading";
  // Browse stays disabled while the current logo is still being looked up, so an upload
  // cannot race the lookup.
  const busy = loading || uploading || removing;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-medium">{t("Organization Logo")}</CardTitle>
        <CardDescription>{t("JPEG, PNG or WebP.")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center">
        {/* Width is the capped axis (it is the scarce one on a phone) and the fixed 3:2 box
            keeps the layout from shifting while loading or on replace; the image is
            contained, never cropped or stretched, so any logo shape fits, tall ones included.
            The card itself takes the content area's width, like the tables do. */}
        <div className="w-44 shrink-0 sm:w-60">
          <AspectRatio ratio={3 / 2} className="bg-muted overflow-hidden rounded-md border">
            {logo ? (
              <img
                src={fileContentUrl(logo.file_id)}
                alt={t("Organization logo")}
                className="h-full w-full object-contain"
              />
            ) : loading ? null : (
              <div className="text-muted-foreground flex h-full w-full flex-col items-center justify-center gap-1 p-2 text-center text-xs">
                <ImageIcon className="h-6 w-6" aria-hidden="true" />
                <span>{t("No logo uploaded")}</span>
              </div>
            )}
          </AspectRatio>
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED_TYPES}
              className="hidden"
              data-testid="logo-file-input"
              onChange={(event) => {
                const file = event.target.files?.[0];
                // Cleared so choosing the same file again (after a failure) still fires.
                event.target.value = "";
                if (file) onBrowse(file);
              }}
            />
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
            >
              <Upload className="h-4 w-4" aria-hidden="true" />
              {t("Browse…")}
            </Button>

            {logo && (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button type="button" variant="ghost" disabled={busy}>
                    {removing && <Spinner />}
                    {removing ? t("Removing…") : t("Remove", { ns: "common" })}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{t("Remove logo?")}</AlertDialogTitle>
                    <AlertDialogDescription>
                      {t("The organization logo will be deleted.")}
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{t("Cancel", { ns: "common" })}</AlertDialogCancel>
                    <AlertDialogAction onClick={onRemove}>
                      {t("Remove", { ns: "common" })}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
          </div>

          {uploading && (
            <div className="flex flex-col gap-1">
              <Progress value={upload.progress} aria-label={t("Uploading logo")} />
              <span className="text-muted-foreground text-xs">
                {t("Uploading… {{percent}}%", { percent: upload.progress })}
              </span>
            </div>
          )}

          {upload.status === "rejected" && (
            <Alert variant="destructive">
              <AlertTitle>{t("Upload rejected")}</AlertTitle>
              <AlertDescription>{upload.error}</AlertDescription>
            </Alert>
          )}

          {upload.status === "error" && (
            <Alert variant="destructive">
              <AlertTitle>{t("Upload failed")}</AlertTitle>
              <AlertDescription className="flex flex-col items-start gap-2">
                {t("The upload didn't go through. Check your connection and try again.")}
                <Button type="button" size="sm" variant="outline" onClick={onRetry}>
                  {t("Try again")}
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {loadFailed && (
            <Alert variant="destructive">
              <AlertDescription>{t("Couldn't load the logo.")}</AlertDescription>
            </Alert>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
