import {
  closestCenter,
  DndContext,
  type Announcements,
  type DragEndEvent,
  MouseSensor,
  TouchSensor,
  type UniqueIdentifier,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { rectSortingStrategy, SortableContext, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  AlertCircle,
  AlertTriangle,
  Check,
  ChevronDown,
  GripVertical,
  Redo2,
  RotateCcw,
  Undo2,
  X,
} from "lucide-react";
import type { CSSProperties, KeyboardEvent, ReactNode } from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DEFAULT_TOKENS,
  findSequence,
  formatErrors,
  formatWarnings,
  movableIds,
  NEW_SEQUENCE,
  PRESETS,
  previewStart,
  renderNumber,
  sameTokens,
  sequenceExample,
  tokensFromItems,
  type Chip,
  type EditorAction,
  type EditorItem,
  type EditorState,
  type FormatError,
  type FormatWarning,
} from "@/lib/invoiceNumbering";
import { cn } from "@/lib/utils";
import type { NumberingState, Restart, SequenceToken } from "@/types/invoiceNumbering";

const DIGITS = Array.from({ length: 10 }, (_, i) => i + 1);
const RESTARTS: Restart[] = ["never", "yearly", "monthly", "daily"];

const RESTART_LABELS: Record<Restart, string> = {
  never: "Never",
  yearly: "Yearly",
  monthly: "Monthly",
  daily: "Daily",
};

const RESET_NOTES: Record<Restart, string> = {
  never: "The counter never resets.",
  yearly: "Counter resets every January 1.",
  monthly: "Counter resets on the 1st of each month.",
  daily: "Counter resets every day.",
};

const ERROR_MESSAGES: Record<FormatError, string> = {
  no_sequence: "Invoice numbers may not be unique. Add a sequence.",
  two_sequences: "A format can contain only one sequence.",
  bad_text: "Only letters, numbers, -, / and _ are allowed.",
  too_long: "Invoice numbers cannot exceed 100 characters.",
  too_many: "A format can have at most 50 parts.",
};

const WARNING_MESSAGES: Record<FormatWarning, string> = {
  daily_repeats: "This counter restarts daily, so numbers will repeat on different days.",
  monthly_repeats: "This counter restarts monthly, so numbers will repeat across months.",
  yearly_repeats: "This counter restarts yearly, so numbers will repeat across years.",
};

const DATE_TILES = [
  { type: "year", label: "Year", hint: "The year the invoice is issued, e.g. 2026." },
  { type: "month", label: "Month", hint: "The month the invoice is issued, as two digits." },
  { type: "day", label: "Day", hint: "The day the invoice is issued, as two digits." },
] as const;

// Chips and tiles are 44 px tall on touch screens.
const TOUCH = "pointer-coarse:h-11";

export interface InvoiceNumberingCardViewProps {
  loading: boolean;
  loadFailed: boolean;
  saved: NumberingState | null;
  editor: EditorState;
  dispatch: (action: EditorAction) => void;
  /** Which request is in flight; the actions are locked while one runs. */
  busy: "format" | "next" | null;
  today: Date;
  onSave: () => void;
  onRetry: () => void;
  nextNumber: string;
  onNextNumberChange: (value: string) => void;
  onSetNext: () => void;
  nextError: string | null;
}

export function InvoiceNumberingCardView({
  loading,
  loadFailed,
  saved,
  editor,
  dispatch,
  busy,
  today,
  onSave,
  onRetry,
  nextNumber,
  onNextNumberChange,
  onSetNext,
  nextError,
}: InvoiceNumberingCardViewProps) {
  const { t } = useTranslation(["configuration"]);
  const [sequenceOpen, setSequenceOpen] = useState(false);
  const unavailable = loading || loadFailed || saved === null;
  const disabled = unavailable || busy !== null;

  const tokens = tokensFromItems(editor.items);
  const errors = formatErrors(tokens);
  const warnings = formatWarnings(tokens);
  const sequence = findSequence(tokens);
  const start = previewStart(saved?.tokens ?? DEFAULT_TOKENS, tokens, saved?.next_value ?? 1);
  const preview = sequence
    ? [0, 1, 2].map((i) => renderNumber(tokens, start.value + i, today))
    : [];
  const changed = saved !== null && !sameTokens(tokens, saved.tokens);

  function insertTile(token: Chip["token"]) {
    if (token.type === "sequence" && sequence) {
      setSequenceOpen(true);
      return;
    }
    dispatch({ type: "insert", token });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-medium">{t("Invoice Numbering")}</CardTitle>
        <CardDescription>
          {t(
            "How issued invoices are numbered. Drafts get their number when they are issued.",
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {loadFailed && (
          <Alert variant="destructive">
            <AlertDescription className="flex flex-col items-start gap-2">
              {t("Couldn't load the invoice numbering.")}
              <Button type="button" size="sm" variant="outline" onClick={onRetry}>
                {t("Try again")}
              </Button>
            </AlertDescription>
          </Alert>
        )}

        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium">{t("Presets")}</span>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((preset) => (
              <Button
                key={preset.id}
                type="button"
                variant="outline"
                size="sm"
                className={cn("font-mono", TOUCH)}
                disabled={disabled}
                onClick={() => dispatch({ type: "replace", tokens: preset.tokens })}
              >
                {renderNumber(preset.tokens, 1, today)}
              </Button>
            ))}
          </div>
        </div>

        <TooltipProvider delayDuration={200}>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">{t("Tiles")}</span>
            <div className="flex flex-wrap items-center gap-2">
              {DATE_TILES.map((tile) => (
                <Tile key={tile.type} hint={t(tile.hint)}>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className={TOUCH}
                    disabled={disabled}
                    data-tile
                    // Keeps the caret where it is, so the chip lands there.
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => insertTile({ type: tile.type })}
                  >
                    {t(tile.label)}
                  </Button>
                </Tile>
              ))}
              <span className="bg-border mx-1 h-6 w-px" aria-hidden="true" />
              <Tile
                hint={t("A counter that goes up by one for every invoice: 001, 002, 003, ...")}
              >
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className={TOUCH}
                  disabled={disabled}
                  data-tile
                  aria-description={sequence ? t("Already in the format") : undefined}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => insertTile(NEW_SEQUENCE)}
                >
                  {sequence && <Check className="h-4 w-4" aria-hidden="true" />}
                  {t("Sequence #")}
                </Button>
              </Tile>
            </div>
          </div>
        </TooltipProvider>

        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium" id="numbering-format-label">
            {t("Format")}
          </span>
          <FormatInput
            editor={editor}
            dispatch={dispatch}
            disabled={disabled}
            sequenceOpen={sequenceOpen}
            onSequenceOpenChange={setSequenceOpen}
          />
        </div>

        <div className="flex flex-col gap-1" aria-live="polite">
          <span className="text-sm font-medium">{t("Preview")}</span>
          <p className="font-mono text-sm break-all" data-testid="numbering-preview">
            {preview.length ? preview.join(" → ") : "—"}
          </p>
          {sequence && (
            <p className="text-muted-foreground text-sm">
              {t(RESET_NOTES[sequence.restart])}
              {start.fresh && ` ${t("The new restart period starts its own counter.")}`}
            </p>
          )}
        </div>

        {(errors.length > 0 || warnings.length > 0) && (
          <ul className="flex flex-col gap-1 text-sm">
            {errors.map((error) => (
              <li key={error} className="text-destructive flex items-start gap-2">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <span>
                  <span className="sr-only">{t("Error")}: </span>
                  {t(ERROR_MESSAGES[error])}
                </span>
              </li>
            ))}
            {warnings.map((warning) => (
              <li key={warning} className="flex items-start gap-2">
                <AlertTriangle
                  className="mt-0.5 h-4 w-4 shrink-0 text-amber-600"
                  aria-hidden="true"
                />
                <span>
                  <span className="sr-only">{t("Warning")}: </span>
                  {t(WARNING_MESSAGES[warning])}
                </span>
              </li>
            ))}
          </ul>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={TOUCH}
            disabled={disabled || editor.past.length === 0}
            onClick={() => dispatch({ type: "undo" })}
          >
            <Undo2 className="h-4 w-4" aria-hidden="true" />
            {t("Undo")}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={TOUCH}
            disabled={disabled || editor.future.length === 0}
            onClick={() => dispatch({ type: "redo" })}
          >
            <Redo2 className="h-4 w-4" aria-hidden="true" />
            {t("Redo")}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={TOUCH}
            disabled={disabled}
            onClick={() => dispatch({ type: "replace", tokens: DEFAULT_TOKENS })}
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            {t("Reset to default")}
          </Button>
          <Button
            type="button"
            size="sm"
            className={cn("ml-auto", TOUCH)}
            disabled={disabled || errors.length > 0 || !changed}
            onClick={onSave}
          >
            {busy === "format" && <Spinner />}
            {busy === "format" ? t("Saving…", { ns: "common" }) : t("Save", { ns: "common" })}
          </Button>
        </div>

        <div className="flex flex-col gap-2 border-t pt-4">
          <Label htmlFor="next-number">{t("Next number")}</Label>
          <p className="text-muted-foreground text-sm">
            {t(
              "The sequence value the next issued invoice receives, e.g. to continue from another system.",
            )}
          </p>
          <div className="flex flex-wrap items-start gap-2">
            <Input
              id="next-number"
              type="number"
              inputMode="numeric"
              min={0}
              className={cn("w-40 tabular-nums", TOUCH)}
              value={nextNumber}
              disabled={disabled}
              aria-invalid={!!nextError}
              onChange={(event) => onNextNumberChange(event.target.value)}
            />
            <Button
              type="button"
              variant="outline"
              className={TOUCH}
              disabled={disabled || !/^\d+$/.test(nextNumber)}
              onClick={onSetNext}
            >
              {busy === "next" && <Spinner />}
              {t("Set")}
            </Button>
          </div>
          {nextError && <p className="text-destructive text-sm">{nextError}</p>}
        </div>
      </CardContent>
    </Card>
  );
}

function Tile({ hint, children }: { hint: string; children: ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent>{hint}</TooltipContent>
    </Tooltip>
  );
}

/** How a chip reads on screen and to a screen reader. */
function useChipText() {
  const { t } = useTranslation(["configuration"]);
  const restartText = (restart: Restart) =>
    restart === "never" ? t("never restarts") : t(RESTART_LABELS[restart]).toLowerCase();
  return {
    label(token: Chip["token"]): string {
      switch (token.type) {
        case "year":
          return t("Year");
        case "month":
          return t("Month");
        case "day":
          return t("Day");
        case "sequence":
          return t("Sequence · {{digits}} digits · {{restart}}", {
            digits: token.digits,
            restart: restartText(token.restart),
          });
      }
    },
    announce(token: Chip["token"]): string {
      if (token.type !== "sequence") return this.label(token);
      return t("Sequence, {{digits}} digits, {{restart}}", {
        digits: token.digits,
        restart: restartText(token.restart),
      });
    },
  };
}

interface FormatInputProps {
  editor: EditorState;
  dispatch: (action: EditorAction) => void;
  disabled: boolean;
  sequenceOpen: boolean;
  onSequenceOpenChange: (open: boolean) => void;
}

/** The format as text slots and chips. Every caret position is inside a text slot, which
 * keeps typing between chips simple; chips and non-empty texts can be dragged. */
function FormatInput({
  editor,
  dispatch,
  disabled,
  sequenceOpen,
  onSequenceOpenChange,
}: FormatInputProps) {
  const { t } = useTranslation(["configuration"]);
  const chipText = useChipText();
  const ids = movableIds(editor.items);
  const isEmpty =
    editor.items.length === 1 && editor.items[0].kind === "text" && !editor.items[0].value;

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
    // A short press before a touch drag starts, so a swipe still scrolls the page.
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
  );

  const describe = (id: UniqueIdentifier | undefined) => {
    const item = editor.items.find((candidate) => candidate.id === id);
    if (!item) return "";
    return item.kind === "text" ? item.value : chipText.announce(item.token);
  };
  const announcements: Announcements = {
    onDragStart: ({ active }) => t("Picked up {{name}}.", { name: describe(active.id) }),
    onDragOver: ({ active, over }) =>
      over
        ? t("{{name}} was moved over {{target}}.", {
            name: describe(active.id),
            target: describe(over.id),
          })
        : "",
    onDragEnd: ({ active }) => t("{{name}} was dropped.", { name: describe(active.id) }),
    onDragCancel: ({ active }) =>
      t("Moving was cancelled. {{name}} was dropped.", { name: describe(active.id) }),
  };

  function handleDragEnd({ active, over }: DragEndEvent) {
    if (over && active.id !== over.id) {
      dispatch({ type: "reorder", activeId: String(active.id), overId: String(over.id) });
    }
  }

  // Alt with an arrow moves the focused chip or text one place.
  function moveKeys(event: KeyboardEvent, id: string) {
    if (!event.altKey || (event.key !== "ArrowLeft" && event.key !== "ArrowRight"))
      return false;
    event.preventDefault();
    dispatch({ type: "move", id, direction: event.key === "ArrowLeft" ? -1 : 1 });
    return true;
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
      accessibility={{
        announcements,
        screenReaderInstructions: {
          draggable: t(
            "To move a part of the format, drag it, or focus it and press Alt with the left or right arrow.",
          ),
        },
      }}
    >
      <SortableContext items={ids} strategy={rectSortingStrategy}>
        <div
          role="group"
          aria-labelledby="numbering-format-label"
          data-numbering-format
          className={cn(
            "border-input flex min-h-11 flex-wrap items-center gap-1 rounded-md border px-2 py-1.5",
            disabled && "opacity-50",
          )}
        >
          {editor.items.map((item, index) =>
            item.kind === "text" ? (
              <TextSlotInput
                key={item.id}
                item={item}
                index={index}
                movable={!!item.value}
                placeholder={
                  isEmpty
                    ? t("Click a tile or type to start building your format.")
                    : undefined
                }
                disabled={disabled}
                dispatch={dispatch}
                onMoveKeys={(event) => moveKeys(event, item.id)}
              />
            ) : (
              <ChipItem
                key={item.id}
                item={item}
                disabled={disabled}
                dispatch={dispatch}
                sequenceOpen={sequenceOpen}
                onSequenceOpenChange={onSequenceOpenChange}
                onMoveKeys={(event) => moveKeys(event, item.id)}
              />
            ),
          )}
        </div>
      </SortableContext>
    </DndContext>
  );
}

function useSortableStyle(id: string, enabled: boolean) {
  const sortable = useSortable({ id, disabled: !enabled });
  const style: CSSProperties = {
    transform: CSS.Translate.toString(sortable.transform),
    transition: sortable.transition,
    opacity: sortable.isDragging ? 0.6 : 1,
  };
  return { ...sortable, style };
}

interface TextSlotInputProps {
  item: Extract<EditorItem, { kind: "text" }>;
  index: number;
  movable: boolean;
  placeholder?: string;
  disabled: boolean;
  dispatch: (action: EditorAction) => void;
  onMoveKeys: (event: KeyboardEvent) => boolean;
}

function TextSlotInput({
  item,
  index,
  movable,
  placeholder,
  disabled,
  dispatch,
  onMoveKeys,
}: TextSlotInputProps) {
  const { t } = useTranslation(["configuration"]);
  // One useSortable per id: the wrapper owns it and the grip borrows it.
  const { setNodeRef, setActivatorNodeRef, attributes, listeners, style } = useSortableStyle(
    item.id,
    movable && !disabled,
  );
  // Wide enough for its text, and still a target when empty.
  const width = placeholder ? "100%" : `${Math.max(item.value.length, 1) + 1}ch`;

  return (
    <span
      ref={setNodeRef}
      style={style}
      className={cn("flex items-center", placeholder && "flex-1")}
    >
      {movable && !disabled && (
        <button
          type="button"
          ref={setActivatorNodeRef}
          className="text-muted-foreground cursor-grab touch-none"
          aria-label={t("Move the text {{text}}", { text: item.value })}
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      )}
      <input
        type="text"
        value={item.value}
        disabled={disabled}
        placeholder={placeholder}
        aria-label={index === 0 ? t("Text at the start") : t("Text")}
        className={cn(
          "focus-visible:ring-ring h-8 rounded-sm bg-transparent px-0.5 font-mono text-sm outline-none focus-visible:ring-2",
          TOUCH,
          placeholder && "placeholder:text-muted-foreground placeholder:font-sans",
        )}
        style={{ width }}
        onChange={(event) =>
          dispatch({
            type: "type",
            slotId: item.id,
            value: event.target.value,
            offset: event.target.selectionStart ?? event.target.value.length,
          })
        }
        onSelect={(event) =>
          dispatch({
            type: "focus",
            caret: { slotId: item.id, offset: event.currentTarget.selectionStart ?? 0 },
          })
        }
        onFocus={(event) =>
          dispatch({
            type: "focus",
            caret: { slotId: item.id, offset: event.currentTarget.selectionStart ?? 0 },
          })
        }
        onBlur={(event) => {
          // The caret survives a move to a tile (so the chip lands where the user was typing)
          // or to another part of the format; it is cleared only when focus leaves both.
          const to = event.relatedTarget as HTMLElement | null;
          if (!to?.closest("[data-tile], [data-numbering-format]")) {
            dispatch({ type: "focus", caret: null });
          }
        }}
        onKeyDown={(event) => {
          if (movable && onMoveKeys(event)) return;
          const input = event.currentTarget;
          if (
            event.key === "Backspace" &&
            input.selectionStart === 0 &&
            input.selectionEnd === 0
          ) {
            event.preventDefault();
            dispatch({ type: "backspace", slotId: item.id });
          }
        }}
      />
    </span>
  );
}

interface ChipItemProps {
  item: Chip;
  disabled: boolean;
  dispatch: (action: EditorAction) => void;
  sequenceOpen: boolean;
  onSequenceOpenChange: (open: boolean) => void;
  onMoveKeys: (event: KeyboardEvent) => boolean;
}

function ChipItem({
  item,
  disabled,
  dispatch,
  sequenceOpen,
  onSequenceOpenChange,
  onMoveKeys,
}: ChipItemProps) {
  const { t } = useTranslation(["configuration"]);
  const chipText = useChipText();
  const { setNodeRef, attributes, listeners, style } = useSortableStyle(item.id, !disabled);
  const isSequence = item.token.type === "sequence";
  const label = chipText.label(item.token);

  const labelButton = (
    <button
      type="button"
      disabled={disabled}
      className="focus-visible:ring-ring max-w-[16rem] cursor-grab touch-none truncate outline-none focus-visible:ring-2"
      title={label}
      aria-label={chipText.announce(item.token)}
      aria-haspopup={isSequence ? "dialog" : undefined}
      {...attributes}
      {...listeners}
      onKeyDown={(event) => {
        // Enter and Space stay with the button (the sequence's settings open); moving
        // by keyboard is Alt with an arrow.
        onMoveKeys(event);
      }}
    >
      {label}
    </button>
  );

  const chip = (
    <span
      ref={setNodeRef}
      style={style}
      className={cn(
        "flex h-8 max-w-full items-center gap-1 rounded-md border pl-2 text-sm",
        TOUCH,
        isSequence ? "border-primary bg-primary/10" : "bg-secondary",
      )}
    >
      {isSequence ? <PopoverTrigger asChild>{labelButton}</PopoverTrigger> : labelButton}
      {isSequence && <ChevronDown className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />}
      <button
        type="button"
        disabled={disabled}
        className="hover:bg-muted flex h-full items-center rounded-r-md px-1"
        aria-label={t("Remove {{part}}", { part: label })}
        onClick={() => dispatch({ type: "remove", id: item.id })}
      >
        <X className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </span>
  );

  if (item.token.type !== "sequence") return chip;
  return (
    // Modal: focus stays inside while it is open, and returns to the chip when it closes.
    <Popover open={sequenceOpen} onOpenChange={onSequenceOpenChange} modal>
      {chip}
      <PopoverContent className="w-80" align="start">
        <SequenceSettings
          token={item.token}
          onChange={(patch) => dispatch({ type: "sequence", patch })}
        />
      </PopoverContent>
    </Popover>
  );
}

function SequenceSettings({
  token,
  onChange,
}: {
  token: SequenceToken;
  onChange: (patch: Partial<Omit<SequenceToken, "type">>) => void;
}) {
  const { t } = useTranslation(["configuration"]);
  const restartHint =
    token.restart === "never"
      ? t("Never restarts: {{example}}", { example: sequenceExample(token) })
      : t(
          "Restarts at {{start}} every {{period}}: {{first}}, {{second}}, ... then back to {{first}}.",
          {
            start: token.start_at,
            period: t({ yearly: "year", monthly: "month", daily: "day" }[token.restart]),
            first: String(token.start_at).padStart(token.digits, "0"),
            second: String(token.start_at + 1).padStart(token.digits, "0"),
          },
        );

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm font-medium">{t("Sequence")}</p>
      <div className="flex flex-col gap-1">
        <Label id="sequence-digits">{t("Digits")}</Label>
        <ToggleGroup
          type="single"
          aria-labelledby="sequence-digits"
          className="flex-wrap justify-start"
          value={String(token.digits)}
          onValueChange={(value) => value && onChange({ digits: Number(value) })}
        >
          {DIGITS.map((digits) => (
            <ToggleGroupItem
              key={digits}
              value={String(digits)}
              size="sm"
              className={cn("w-8", TOUCH)}
            >
              {digits}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="sequence-start">{t("Start at")}</Label>
        <Input
          id="sequence-start"
          type="number"
          inputMode="numeric"
          min={0}
          className={cn("w-32", TOUCH)}
          value={token.start_at}
          onChange={(event) => {
            const value = Number(event.target.value);
            if (Number.isInteger(value) && value >= 0) onChange({ start_at: value });
          }}
        />
      </div>
      <div className="flex flex-col gap-1">
        <Label id="sequence-restart">{t("Restart")}</Label>
        <ToggleGroup
          type="single"
          aria-labelledby="sequence-restart"
          className="flex-wrap justify-start"
          value={token.restart}
          onValueChange={(value) => value && onChange({ restart: value as Restart })}
        >
          {RESTARTS.map((restart) => (
            <ToggleGroupItem key={restart} value={restart} size="sm" className={TOUCH}>
              {t(RESTART_LABELS[restart])}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <p className="text-muted-foreground text-sm">{restartHint}</p>
      </div>
      <p className="text-sm">
        {t("Example")}: <span className="font-mono">{sequenceExample(token)}</span>
      </p>
      <p className="text-muted-foreground text-xs">
        {t("A value with more digits than set is shown in full, never cut.")}
      </p>
    </div>
  );
}
