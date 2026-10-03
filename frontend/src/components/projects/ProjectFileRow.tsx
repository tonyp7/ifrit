import { Trash2, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { FileTagPicker } from "@/components/projects/FileTagPicker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatFileSize } from "@/lib/format";
import { resolveFileIcon } from "@/lib/fileIcons";
import { availableTags } from "@/lib/projectFiles";
import { cn } from "@/lib/utils";
import type { FileTag, ProjectFile } from "@/types/file";

export interface ProjectFileRowProps {
  file: ProjectFile;
  vocabulary: FileTag[];
  /** Closed project: every control is shown disabled, the download stays live. */
  readOnly: boolean;
  onDownload: (file: ProjectFile) => void;
  onDelete: (file: ProjectFile) => void;
  onAddTag: (file: ProjectFile, tag: FileTag) => void;
  onRemoveTag: (file: ProjectFile, tag: FileTag) => void;
}

export function ProjectFileRow({
  file,
  vocabulary,
  readOnly,
  onDownload,
  onDelete,
  onAddTag,
  onRemoveTag,
}: ProjectFileRowProps) {
  const { t } = useTranslation(["projects"]);
  const { Icon, className: iconColor } = resolveFileIcon({
    contentType: file.content_type,
    filename: file.original_filename,
  });

  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 py-2">
      {/* On a phone the name group takes the whole line, which pushes the tags below it. */}
      <div className="flex w-full min-w-0 items-center gap-2 sm:w-auto sm:flex-1">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          disabled={readOnly}
          aria-label={t("Delete file {{name}}", { name: file.original_filename })}
          onClick={() => onDelete(file)}
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </Button>
        <Icon className={cn("h-5 w-5 shrink-0", iconColor)} aria-hidden="true" />
        <Button
          type="button"
          variant="link"
          className="text-foreground h-auto min-w-0 justify-start p-0"
          onClick={() => onDownload(file)}
        >
          <span className="truncate">{file.original_filename}</span>
        </Button>
        <span className="text-muted-foreground shrink-0 text-xs">
          {formatFileSize(file.size_bytes)}
        </span>
      </div>

      <div className="flex w-full flex-wrap items-center gap-1.5 sm:w-auto">
        {file.tags.map((tag) => (
          <Badge key={tag.id} variant="secondary" className="gap-1 pr-1">
            {tag.name}
            {/* A real button, always visible, so keyboard and touch users reach it too. */}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="hover:bg-foreground/10 h-4 w-4 rounded-full p-0"
              disabled={readOnly}
              aria-label={t("Remove tag {{tag}}", { tag: tag.name })}
              onClick={() => onRemoveTag(file, tag)}
            >
              <X className="h-3 w-3" aria-hidden="true" />
            </Button>
          </Badge>
        ))}
        <FileTagPicker
          available={availableTags(vocabulary, file.tags)}
          disabled={readOnly}
          onSelect={(tag) => onAddTag(file, tag)}
        />
      </div>
    </li>
  );
}
