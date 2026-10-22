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
import { MoreHorizontal, Plus, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

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
import { SortableRow } from "@/components/SortableRow";
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
                      <TableCell>
                        {readOnly ? (
                          milestone.description
                        ) : (
                          <RowButton onClick={() => onEdit(milestone)}>
                            {milestone.description}
                          </RowButton>
                        )}
                      </TableCell>
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
                                <DropdownMenuItem onClick={() => onEdit(milestone)}>
                                  {t("Edit", { ns: "common" })}
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => onDuplicate(milestone)}>
                                  {t("Duplicate", { ns: "common" })}
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
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
