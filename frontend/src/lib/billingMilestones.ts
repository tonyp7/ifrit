import { stripGrouping } from "@/lib/format";
import {
  milestoneDecimals,
  percentToValue,
  roundDecimal,
  valueToPercent,
} from "@/lib/milestoneMath";
import { parseDayKey, toDayKey } from "@/lib/timesheetDates";
import type { BillingMilestone, ProjectType } from "@/types/project";

// The pure rules behind the billing milestones section, its dialog and the project form's
// type picker, kept apart from the components so they can be tested without a browser.

const DECIMAL_INPUT = /^\d+(\.\d+)?$/;

/** The list after dropping `activeId` onto `overId`'s place; unchanged when either is
 * unknown or they are the same row. Works on any list of rows with an `id`: the billing
 * milestones and the project references reorder the same way. */
export function moveMilestone<T extends { id: string }>(
  milestones: T[],
  activeId: string,
  overId: string,
): T[] {
  const from = milestones.findIndex((m) => m.id === activeId);
  const to = milestones.findIndex((m) => m.id === overId);
  if (from === -1 || to === -1 || from === to) return milestones;
  const next = [...milestones];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

/** Shows the order after a drop at once, then saves it; if saving fails, shows `current`
 * again and rethrows so the caller can report the error. */
export async function reorderOptimistically<T extends { id: string }>(
  current: T[],
  activeId: string,
  overId: string,
  save: (ids: string[]) => Promise<unknown>,
  show: (rows: T[]) => void,
): Promise<void> {
  const next = moveMilestone(current, activeId, overId);
  if (next === current) return;
  show(next);
  try {
    await save(next.map((m) => m.id));
  } catch (err) {
    show(current);
    throw err;
  }
}

/** Whether leaving `currentType` for `nextType` must be confirmed first: it deletes the
 * milestones on the next save, which only matters when the saved project has some. */
export function typeChangeNeedsConfirmation(
  currentType: ProjectType,
  nextType: ProjectType,
  savedMilestoneCount: number,
): boolean {
  return (
    currentType === "fixed_price" && nextType !== "fixed_price" && savedMilestoneCount > 0
  );
}

/** Whether `input` (as typed, possibly comma-grouped) is a non-negative decimal. */
export function isDecimalInput(input: string): boolean {
  return DECIMAL_INPUT.test(stripGrouping(input).trim());
}

/** Whether `input` has no more decimals than the currency allows. */
export function fitsCurrency(input: string, minorUnit: number | null | undefined): boolean {
  const fraction = stripGrouping(input).trim().split(".")[1] ?? "";
  return fraction.replace(/0+$/, "").length <= milestoneDecimals(minorUnit);
}

/** The Value field after typing `percentInput` into %: the contract value's share,
 * rounded to the currency; empty while the input is not (yet) a number. */
export function valueFromPercentInput(
  percentInput: string,
  contractValue: string,
  minorUnit: number | null | undefined,
): string {
  if (!isDecimalInput(percentInput)) return "";
  return percentToValue(contractValue, stripGrouping(percentInput).trim(), minorUnit) ?? "";
}

/** The % field after typing `valueInput` into Value; empty while the input is not a
 * number or there is no contract value to compare with. */
export function percentFromValueInput(valueInput: string, contractValue: string): string {
  if (!isDecimalInput(valueInput)) return "";
  return valueToPercent(stripGrouping(valueInput).trim(), contractValue) ?? "";
}

export interface MilestoneFormValues {
  description: string;
  dueDate: string | null;
  percent: string;
  value: string;
}

export const BLANK_MILESTONE_FORM: MilestoneFormValues = {
  description: "",
  dueDate: null,
  percent: "",
  value: "",
};

/** The dialog's starting values for an existing milestone (Edit, Duplicate): the stored
 * value at the currency's precision (it may hold more after a currency change) and its %
 * recomputed from that value against today's contract value. */
export function milestoneToFormValues(
  milestone: BillingMilestone,
  contractValue: string,
  minorUnit: number | null | undefined,
): MilestoneFormValues {
  const value = roundDecimal(milestone.value, milestoneDecimals(minorUnit)) ?? milestone.value;
  return {
    description: milestone.description,
    dueDate: milestone.due_date,
    percent: valueToPercent(value, contractValue) ?? "",
    value,
  };
}

/** `YYYY-MM-DD` for a date picked in the calendar, `null` when it was cleared. Built from
 * the local date parts, so a date picked in a time zone behind UTC is not moved a day. */
export function dueDateFromSelection(selected: Date | undefined): string | null {
  return selected ? toDayKey(selected) : null;
}

/** A due date as the user reads it, in their language, with the year (e.g. "15 Jan 2027"). */
export function formatDueDate(dayKey: string): string {
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(parseDayKey(dayKey));
}
