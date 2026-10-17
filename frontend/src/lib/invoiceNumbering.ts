import type { NumberingToken, Restart, SequenceToken } from "@/types/invoiceNumbering";

// The invoice numbering format editor, as pure functions: rendering, validation, presets,
// and the reducer behind the chip input. Its rules mirror the server's, which has the last
// word on save.

export const MAX_NUMBER_LENGTH = 100;
export const MAX_TOKENS = 50;
const TEXT = /^[A-Za-z0-9/_-]+$/;

export const NEW_SEQUENCE: SequenceToken = {
  type: "sequence",
  digits: 4,
  start_at: 1,
  restart: "never",
};

export const DEFAULT_TOKENS: NumberingToken[] = [
  { type: "text", value: "INV-" },
  { type: "year" },
  { type: "text", value: "-" },
  { type: "sequence", digits: 4, start_at: 1, restart: "yearly" },
];

export interface Preset {
  id: string;
  tokens: NumberingToken[];
}

export const PRESETS: Preset[] = [
  {
    id: "plain",
    tokens: [
      { type: "text", value: "INV-" },
      { type: "sequence", digits: 5, start_at: 1, restart: "never" },
    ],
  },
  {
    id: "yearly",
    tokens: [
      { type: "year" },
      { type: "text", value: "-" },
      { type: "sequence", digits: 4, start_at: 1, restart: "yearly" },
    ],
  },
  {
    id: "monthly",
    tokens: [
      { type: "year" },
      { type: "month" },
      { type: "text", value: "-" },
      { type: "sequence", digits: 3, start_at: 1, restart: "monthly" },
    ],
  },
];

const pad = (n: number, width: number) => String(n).padStart(width, "0");

/** The number for sequence `value` on `day`. A value wider than its digits is written in
 * full, never truncated. Dates are the browser's; the server renders the real number. */
export function renderNumber(tokens: NumberingToken[], value: number, day: Date): string {
  return tokens
    .map((token) => {
      switch (token.type) {
        case "text":
          return token.value;
        case "year":
          return String(day.getFullYear());
        case "month":
          return pad(day.getMonth() + 1, 2);
        case "day":
          return pad(day.getDate(), 2);
        case "sequence":
          return pad(value, token.digits);
      }
    })
    .join("");
}

export function findSequence(tokens: NumberingToken[]): SequenceToken | undefined {
  return tokens.find((token): token is SequenceToken => token.type === "sequence");
}

/** `00001, 00002, 00003, ...` for a sequence's popover. */
export function sequenceExample(sequence: SequenceToken): string {
  return [0, 1, 2].map((i) => pad(sequence.start_at + i, sequence.digits)).join(", ") + ", ...";
}

const WIDTH: Record<"year" | "month" | "day", number> = { year: 4, month: 2, day: 2 };

/** The longest number the format can produce, with the sequence at its digits. */
export function longestLength(tokens: NumberingToken[]): number {
  return tokens.reduce((total, token) => {
    if (token.type === "text") return total + token.value.length;
    if (token.type === "sequence") return total + token.digits;
    return total + WIDTH[token.type];
  }, 0);
}

export type FormatError = "no_sequence" | "two_sequences" | "bad_text" | "too_long" | "too_many";
export type FormatWarning = "daily_repeats" | "monthly_repeats" | "yearly_repeats";

/** What blocks saving, the same rules as the server. */
export function formatErrors(tokens: NumberingToken[]): FormatError[] {
  const errors: FormatError[] = [];
  const sequences = tokens.filter((token) => token.type === "sequence").length;
  if (sequences === 0) errors.push("no_sequence");
  if (sequences > 1) errors.push("two_sequences");
  if (tokens.some((token) => token.type === "text" && !TEXT.test(token.value))) {
    errors.push("bad_text");
  }
  if (longestLength(tokens) > MAX_NUMBER_LENGTH) errors.push("too_long");
  if (tokens.length > MAX_TOKENS) errors.push("too_many");
  return errors;
}

// The date tiles a restart period needs so that numbers from different periods differ.
const NEEDED: Record<Exclude<Restart, "never">, ("year" | "month" | "day")[]> = {
  daily: ["year", "month", "day"],
  monthly: ["year", "month"],
  yearly: ["year"],
};

/** What does not block saving but repeats numbers: a counter that restarts without the
 * date tiles of its own period. */
export function formatWarnings(tokens: NumberingToken[]): FormatWarning[] {
  const sequence = findSequence(tokens);
  if (!sequence || sequence.restart === "never") return [];
  const present = new Set(tokens.map((token) => token.type));
  const missing = NEEDED[sequence.restart].some((type) => !present.has(type));
  return missing ? [`${sequence.restart}_repeats` as FormatWarning] : [];
}

// --- the chip input --------------------------------------------------------------

export interface TextSlot {
  kind: "text";
  id: string;
  value: string;
}

export interface Chip {
  kind: "chip";
  id: string;
  token: Exclude<NumberingToken, { type: "text" }>;
}

export type EditorItem = TextSlot | Chip;

let nextId = 0;
function newId(): string {
  nextId += 1;
  return `n${nextId}`;
}

/**
 * The input always alternates text slot, chip, text slot ... text slot (a slot may be
 * empty), so every caret position is inside some text slot: typing edits that slot, a tile
 * splits it, and Backspace at its start removes the chip before it.
 */
export function normalize(items: EditorItem[]): EditorItem[] {
  // Drop empty texts and join neighbouring ones, keeping the first one's id.
  const compact: EditorItem[] = [];
  for (const item of items) {
    if (item.kind === "text" && !item.value) continue;
    const previous = compact[compact.length - 1];
    if (item.kind === "text" && previous?.kind === "text") {
      compact[compact.length - 1] = { ...previous, value: previous.value + item.value };
    } else {
      compact.push(item);
    }
  }
  // Re-add an empty slot wherever two chips meet and at both ends.
  const result: EditorItem[] = [];
  for (const item of compact) {
    const previous = result[result.length - 1];
    if (item.kind === "chip" && previous?.kind !== "text") {
      result.push({ kind: "text", id: newId(), value: "" });
    }
    result.push(item);
  }
  if (result[result.length - 1]?.kind !== "text") {
    result.push({ kind: "text", id: newId(), value: "" });
  }
  return result;
}

export function itemsFromTokens(tokens: NumberingToken[]): EditorItem[] {
  return normalize(
    tokens.map((token) =>
      token.type === "text"
        ? { kind: "text", id: newId(), value: token.value }
        : { kind: "chip", id: newId(), token },
    ),
  );
}

export function tokensFromItems(items: EditorItem[]): NumberingToken[] {
  return normalize(items)
    .filter((item) => item.kind === "chip" || item.value)
    .map((item) => (item.kind === "text" ? { type: "text", value: item.value } : item.token));
}

export interface Caret {
  slotId: string;
  offset: number;
}

export interface EditorState {
  items: EditorItem[];
  /** Where a tile goes; null puts it at the end. */
  caret: Caret | null;
  past: EditorItem[][];
  future: EditorItem[][];
  /** The slot whose typing is gathered into the current history entry. */
  typingIn: string | null;
}

export type EditorAction =
  | { type: "load"; tokens: NumberingToken[] }
  | { type: "focus"; caret: Caret | null }
  | { type: "type"; slotId: string; value: string; offset: number }
  | { type: "insert"; token: Chip["token"] }
  | { type: "backspace"; slotId: string }
  | { type: "remove"; id: string }
  | { type: "move"; id: string; direction: -1 | 1 }
  | { type: "reorder"; activeId: string; overId: string }
  | { type: "sequence"; patch: Partial<Omit<SequenceToken, "type">> }
  | { type: "replace"; tokens: NumberingToken[] }
  | { type: "undo" }
  | { type: "redo" };

export function initialEditorState(tokens: NumberingToken[]): EditorState {
  return { items: itemsFromTokens(tokens), caret: null, past: [], future: [], typingIn: null };
}

function commit(state: EditorState, items: EditorItem[], caret: Caret | null = state.caret): EditorState {
  return {
    items,
    caret,
    past: [...state.past, state.items],
    future: [],
    typingIn: null,
  };
}

/** The items that can be dragged: chips and texts with content, never the empty slots. */
export function movableIds(items: EditorItem[]): string[] {
  return items.filter((item) => item.kind === "chip" || item.value).map((item) => item.id);
}

function moveTo(items: EditorItem[], from: number, to: number): EditorItem[] {
  const movable = items.filter((item) => item.kind === "chip" || item.value);
  if (from < 0 || to < 0 || from >= movable.length || to >= movable.length) return items;
  const next = [...movable];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return normalize(next);
}

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case "load":
      return initialEditorState(action.tokens);
    case "focus":
      return { ...state, caret: action.caret, typingIn: action.caret ? state.typingIn : null };
    case "type": {
      const items = state.items.map((item) =>
        item.id === action.slotId && item.kind === "text" ? { ...item, value: action.value } : item,
      );
      const caret = { slotId: action.slotId, offset: action.offset };
      // Typing within one slot is one undo step, until focus leaves it.
      if (state.typingIn === action.slotId) return { ...state, items, caret };
      return { ...commit(state, items, caret), typingIn: action.slotId };
    }
    case "insert": {
      if (action.token.type === "sequence" && state.items.some((i) => i.kind === "chip" && i.token.type === "sequence")) {
        return state;
      }
      const chip: Chip = { kind: "chip", id: newId(), token: action.token };
      const at = state.caret ? state.items.findIndex((i) => i.id === state.caret?.slotId) : -1;
      if (at < 0) {
        const items = normalize([...state.items, chip]);
        return commit(state, items, null);
      }
      const slot = state.items[at] as TextSlot;
      const offset = Math.min(state.caret?.offset ?? slot.value.length, slot.value.length);
      const after: TextSlot = { kind: "text", id: newId(), value: slot.value.slice(offset) };
      const items = normalize([
        ...state.items.slice(0, at),
        { ...slot, value: slot.value.slice(0, offset) },
        chip,
        after,
        ...state.items.slice(at + 1),
      ]);
      // The caret goes right after the new chip.
      const landing = items[items.findIndex((i) => i.id === chip.id) + 1];
      return commit(state, items, landing ? { slotId: landing.id, offset: 0 } : null);
    }
    case "backspace": {
      const at = state.items.findIndex((i) => i.id === action.slotId);
      if (at < 2 || state.items[at - 1].kind !== "chip") return state;
      const previous = state.items[at - 2] as TextSlot;
      const items = normalize([...state.items.slice(0, at - 1), ...state.items.slice(at)]);
      // The two slots merged under the earlier one's id; the caret sits at the join.
      const merged = items.find((i) => i.id === previous.id) ?? items[0];
      return commit(state, items, { slotId: merged.id, offset: previous.value.length });
    }
    case "remove":
      return commit(state, normalize(state.items.filter((i) => i.id !== action.id)), null);
    case "move": {
      const ids = movableIds(state.items);
      const from = ids.indexOf(action.id);
      const items = moveTo(state.items, from, from + action.direction);
      return items === state.items ? state : commit(state, items);
    }
    case "reorder": {
      const ids = movableIds(state.items);
      const items = moveTo(state.items, ids.indexOf(action.activeId), ids.indexOf(action.overId));
      return items === state.items ? state : commit(state, items);
    }
    case "sequence": {
      const items = state.items.map((item) =>
        item.kind === "chip" && item.token.type === "sequence"
          ? { ...item, token: { ...item.token, ...action.patch } }
          : item,
      );
      return commit(state, items);
    }
    case "replace":
      return commit(state, itemsFromTokens(action.tokens), null);
    case "undo": {
      const previous = state.past[state.past.length - 1];
      if (!previous) return state;
      return {
        items: previous,
        caret: null,
        past: state.past.slice(0, -1),
        future: [state.items, ...state.future],
        typingIn: null,
      };
    }
    case "redo": {
      const [next, ...rest] = state.future;
      if (!next) return state;
      return { items: next, caret: null, past: [...state.past, state.items], future: rest, typingIn: null };
    }
  }
}

/** The value the preview starts from: the server's next value while the restart period is
 * the saved one; a different restart moves to another counter, which starts at the start
 * value. */
export function previewStart(
  saved: NumberingToken[],
  edited: NumberingToken[],
  serverNext: number,
): { value: number; fresh: boolean } {
  const before = findSequence(saved);
  const after = findSequence(edited);
  if (!after) return { value: serverNext, fresh: false };
  if (before && before.restart === after.restart) return { value: serverNext, fresh: false };
  return { value: after.start_at, fresh: true };
}

export function sameTokens(a: NumberingToken[], b: NumberingToken[]): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}
