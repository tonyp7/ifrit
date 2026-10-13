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
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Grip, MoreHorizontal, Plus, TriangleAlert } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
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
import { formatDueDate } from "@/lib/billingMilestones";
import { formatMoney } from "@/lib/format";
import { differsFromContract, sumValues, valueToPercent } from "@/lib/milestoneMath";
import type { BillingMilestone } from "@/types/project";

export interface BillingMilestonesSectionViewProps {
  milestones: BillingMilestone[];
  /** The project's contract value (sum of its service lines), the base of the %. */
  contractValue: string;
  minorUnit: number | null | undefined;
  /** true when the project is `closed`: listed only, no add, reorder or row actions. */
  readOnly: boolean;
  error: string | null;
  onAdd: () => void;
  onEdit: (milestone: BillingMilestone) => void;
  onDuplicate: (milestone: BillingMilestone) => void;
  onDeleteRequest: (milestone: BillingMilestone) => void;
  onReorder: (activeId: string, overId: string) => void;
}

function formatPercent(percent: string | null): string {
  return percent === null ? "—" : `${formatMoney(percent, 2)}%`;
}

// One `useSortable` per row, and the handle borrows it: dnd-kit keeps a single registered
// node per id, written only when a hook mounts, so a second hook for the same id (e.g. in a
// handle that only appears once a second row exists) would overwrite the row's registration
// with an empty node and the row could no longer be dragged until a reload.
function SortableRow({
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
  const { t } = useTranslation("projects");
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

export function BillingMilestonesSectionView({
  milestones,
  contractValue,
  minorUnit,
  readOnly,
  error,
  onAdd,
  onEdit,
  onDuplicate,
  onDeleteRequest,
  onReorder,
}: BillingMilestonesSectionViewProps) {
  const { t } = useTranslation(["projects", "common"]);
  // Nothing to reorder with a single row.
  const sortable = !readOnly && milestones.length > 1;

  const sensors = useSensors(
    useSensor(MouseSensor),
    // A short press before a touch drag starts, so a swipe across the table still scrolls.
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
    // Arrow keys move the picked-up row by one position.
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const describe = (id: UniqueIdentifier | undefined) =>
    milestones.find((m) => m.id === id)?.description ?? "";
  const announcements: Announcements = {
    onDragStart: ({ active }) => t("Picked up {{name}}.", { name: describe(active.id) }),
    onDragOver: ({ active, over }) =>
      over
        ? t("{{name}} was moved over {{target}}.", {
            name: describe(active.id),
            target: describe(over.id),
          })
        : t("{{name}} is no longer over a milestone.", { name: describe(active.id) }),
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

  const total = sumValues(milestones.map((m) => m.value));
  const showWarning =
    milestones.length > 0 && differsFromContract(total, contractValue, minorUnit);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">{t("Billing Milestones")}</h3>
        {!readOnly && (
          <Button type="button" size="sm" variant="outline" onClick={onAdd}>
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            {t("Add", { ns: "common" })}
          </Button>
        )}
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {milestones.length > 0 && (
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
                "To pick up a milestone, press Space or Enter. Use the arrow keys to move it, Space or Enter to drop it, or Escape to cancel.",
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
                  <TableHead>{t("Description")}</TableHead>
                  <TableHead>{t("Due date")}</TableHead>
                  <TableHead className="text-right">%</TableHead>
                  <TableHead className="text-right">{t("Value")}</TableHead>
                  {!readOnly && <TableHead />}
                </TableRow>
              </TableHeader>
              <TableBody>
                <SortableContext
                  items={milestones.map((m) => m.id)}
                  strategy={verticalListSortingStrategy}
                  disabled={!sortable}
                >
                  {milestones.map((milestone) => (
                    <SortableRow
                      key={milestone.id}
                      id={milestone.id}
                      description={milestone.description}
                      sortable={sortable}
                    >
                      <TableCell>{milestone.description}</TableCell>
                      <TableCell>
                        {milestone.due_date ? formatDueDate(milestone.due_date) : ""}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatPercent(valueToPercent(milestone.value, contractValue))}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatMoney(milestone.value, minorUnit)}
                      </TableCell>
                      {!readOnly && (
                        <TableCell>
                          <div className="flex justify-end">
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
                                <DropdownMenuItem onClick={() => onEdit(milestone)}>
                                  {t("Edit", { ns: "common" })}
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => onDuplicate(milestone)}>
                                  {t("Duplicate", { ns: "common" })}
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  className="text-destructive focus:text-destructive"
                                  onClick={() => onDeleteRequest(milestone)}
                                >
                                  {t("Delete", { ns: "common" })}
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </TableCell>
                      )}
                    </SortableRow>
                  ))}
                </SortableContext>
                <TableRow className="font-medium hover:bg-transparent">
                  {sortable && <TableCell />}
                  <TableCell>{t("Total")}</TableCell>
                  <TableCell />
                  <TableCell className="text-right">
                    {formatPercent(valueToPercent(total, contractValue))}
                  </TableCell>
                  <TableCell className="text-right">{formatMoney(total, minorUnit)}</TableCell>
                  {!readOnly && <TableCell />}
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </DndContext>
      )}

      {showWarning && (
        <p className="flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400">
          <TriangleAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
          {t("The sum of all billing milestones differs from the contract value.")}
        </p>
      )}
    </div>
  );
}
