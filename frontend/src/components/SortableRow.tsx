import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Grip } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { TableCell, TableRow } from "@/components/ui/table";

// One `useSortable` per row, and the handle borrows it: dnd-kit keeps a single registered
// node per id, written only when a hook mounts, so a second hook for the same id (e.g. in a
// handle that only appears once a second row exists) would overwrite the row's registration
// with an empty node and the row could no longer be dragged until a reload.
export function SortableRow({
  id,
  description,
  sortable,
  children,
}: {
  id: string;
  description: string;
  /** Whether to show the drag handle cell. */
  sortable: boolean;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });
  const style: CSSProperties = {
    // Translate, not Transform: the scale part would squish the row while it passes rows
    // of a different height.
    transform: CSS.Translate.toString(transform),
    transition,
    position: "relative",
    zIndex: isDragging ? 1 : 0,
    opacity: isDragging ? 0.8 : 1,
  };
  return (
    <TableRow ref={setNodeRef} style={style} data-dragging={isDragging || undefined}>
      {sortable && (
        <TableCell>
          <Button
            ref={setActivatorNodeRef}
            type="button"
            variant="ghost"
            size="sm"
            // touch-action: none hands touch gestures on the handle to the drag sensor; the
            // rest of the row still scrolls the page.
            className="text-muted-foreground h-8 w-8 cursor-grab touch-none p-0"
            aria-label={t("Drag to reorder {{name}}", { name: description })}
            {...attributes}
            {...listeners}
          >
            <Grip className="h-4 w-4" aria-hidden="true" />
          </Button>
        </TableCell>
      )}
      {children}
    </TableRow>
  );
}
