import {
  type Announcements,
  closestCenter,
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  type UniqueIdentifier,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { MoreHorizontal, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import { SortableRow } from "@/components/SortableRow";
import { Button } from "@/components/ui/button";
import { RowButton } from "@/components/data-table/RowControl";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { MAX_PROJECT_REFERENCES, referenceName } from "@/lib/projectReferences";
import type { ProjectReference } from "@/types/project";

export interface ProjectReferencesSectionViewProps {
  references: ProjectReference[];
  /** true when the project is `closed`: listed only, no add, reorder or row actions. */
  readOnly: boolean;
  error: string | null;
  onAdd: () => void;
  onEdit: (reference: ProjectReference) => void;
  onDuplicate: (reference: ProjectReference) => void;
  onDeleteRequest: (reference: ProjectReference) => void;
  onReorder: (activeId: string, overId: string) => void;
}

export function ProjectReferencesSectionView({
  references,
  readOnly,
  error,
  onAdd,
  onEdit,
  onDuplicate,
  onDeleteRequest,
  onReorder,
}: ProjectReferencesSectionViewProps) {
  const { t } = useTranslation(["projects", "common"]);
  // Nothing to reorder with a single row.
  const sortable = !readOnly && references.length > 1;
  const atLimit = references.length >= MAX_PROJECT_REFERENCES;

  const sensors = useSensors(
    useSensor(MouseSensor),
    // A short press before a touch drag starts, so a swipe across the table still scrolls.
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
    // Arrow keys move the picked-up row by one position.
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const describe = (id: UniqueIdentifier | undefined) => {
    const found = references.find((r) => r.id === id);
    return found ? referenceName(found, t) : "";
  };
  const announcements: Announcements = {
    onDragStart: ({ active }) => t("Picked up {{name}}.", { name: describe(active.id) }),
    onDragOver: ({ active, over }) =>
      over
        ? t("{{name}} was moved over {{target}}.", {
            name: describe(active.id),
            target: describe(over.id),
          })
        : t("{{name}} is no longer over a reference.", { name: describe(active.id) }),
    onDragEnd: ({ active, over }) =>
      over
        ? t("{{name}} was dropped over {{target}}.", {
            name: describe(active.id),
            target: describe(over.id),
          })
        : t("{{name}} was dropped.", { name: describe(active.id) }),
    onDragCancel: ({ active }) =>
      t("Reordering was cancelled. {{name}} was dropped.", { name: describe(active.id) }),
  };

  function handleDragEnd({ active, over }: DragEndEvent) {
    if (over && active.id !== over.id) onReorder(String(active.id), String(over.id));
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">{t("Project References")}</h3>
        {!readOnly && (
          <Button type="button" size="sm" variant="outline" disabled={atLimit} onClick={onAdd}>
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            {t("Add", { ns: "common" })}
          </Button>
        )}
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {references.length > 0 && (
        // DndContext renders wrapper elements of its own, which are not valid inside a
        // <table>: it wraps the whole table instead.
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          modifiers={[restrictToVerticalAxis]}
          onDragEnd={handleDragEnd}
          accessibility={{
            announcements,
            screenReaderInstructions: {
              draggable: t(
                "To pick up a reference, press Space or Enter. Use the arrow keys to move it, Space or Enter to drop it, or Escape to cancel.",
              ),
            },
          }}
        >
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  {sortable && (
                    <TableHead className="w-10">
                      <span className="sr-only">{t("Order")}</span>
                    </TableHead>
                  )}
                  <TableHead>{t("Reference Name")}</TableHead>
                  <TableHead>{t("Value")}</TableHead>
                  {!readOnly && <TableHead />}
                </TableRow>
              </TableHeader>
              <TableBody>
                <SortableContext
                  items={references.map((r) => r.id)}
                  strategy={verticalListSortingStrategy}
                  disabled={!sortable}
                >
                  {references.map((reference) => {
                    const name = referenceName(reference, t);
                    return (
                      <SortableRow
                        key={reference.id}
                        id={reference.id}
                        description={name}
                        sortable={sortable}
                      >
                        <TableCell>
                          {readOnly ? (
                            name
                          ) : (
                            <RowButton onClick={() => onEdit(reference)}>{name}</RowButton>
                          )}
                        </TableCell>
                        <TableCell className="break-words">{reference.value}</TableCell>
                        {!readOnly && (
                          <TableCell>
                            <div className="relative z-10 flex justify-end">
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                    <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                                    <span className="sr-only">
                                      {t("Actions", { ns: "common" })}
                                    </span>
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem onClick={() => onEdit(reference)}>
                                    {t("Edit", { ns: "common" })}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => onDuplicate(reference)}>
                                    {t("Duplicate", { ns: "common" })}
                                  </DropdownMenuItem>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem
                                    className="text-destructive focus:text-destructive"
                                    onClick={() => onDeleteRequest(reference)}
                                  >
                                    {t("Delete", { ns: "common" })}
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </div>
                          </TableCell>
                        )}
                      </SortableRow>
                    );
                  })}
                </SortableContext>
              </TableBody>
            </Table>
          </div>
        </DndContext>
      )}

      {!readOnly && atLimit && (
        <p className="text-muted-foreground text-sm">
          {t("Maximum of {{count}} references reached.", { count: MAX_PROJECT_REFERENCES })}
        </p>
      )}
    </div>
  );
}
