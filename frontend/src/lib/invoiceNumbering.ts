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
  return (
    [0, 1, 2].map((i) => pad(sequence.start_at + i, sequence.digits)).join(", ") + ", ..."
  );
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

export type FormatError =
  "no_sequence" | "two_sequences" | "bad_text" | "too_long" | "too_many";
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

/** One part of the format as the editor holds it: a chip with a stable id. A text token is a
 * Label chip, fixed text typed into the chip itself. */
export interface EditorItem {
  id: string;
  token: NumberingToken;
}

let nextId = 0;
function newId(): string {
  nextId += 1;
  return `n${nextId}`;
}

export function itemsFromTokens(tokens: NumberingToken[]): EditorItem[] {
  return tokens.map((token) => ({ id: newId(), token }));
}

/** The saved format: empty Labels dropped and neighbouring ones joined, as the server stores
 * them. The editor keeps them apart so that each can still be removed on its own. */
export function tokensFromItems(items: EditorItem[]): NumberingToken[] {
  const tokens: NumberingToken[] = [];
  for (const { token } of items) {
    if (token.type === "text") {
      if (!token.value) continue;
      const previous = tokens[tokens.length - 1];
      if (previous?.type === "text") {
        tokens[tokens.length - 1] = { type: "text", value: previous.value + token.value };
        continue;
      }
    }
    tokens.push(token);
  }
  return tokens;
}

export interface EditorState {
  items: EditorItem[];
  past: EditorItem[][];
  future: EditorItem[][];
  /** The Label whose typing is gathered into the current history entry. */
  typingIn: string | null;
  /** A Label just added, whose text box should take focus; null once anything else happens. */
  focusId: string | null;
}

export type EditorAction =
  | { type: "load"; tokens: NumberingToken[] }
  | { type: "insert"; token: NumberingToken }
  | { type: "label"; id: string; value: string }
  | { type: "prune" }
  | { type: "remove"; id: string }
  | { type: "move"; id: string; direction: -1 | 1 }
  | { type: "reorder"; activeId: string; overId: string }
  | { type: "sequence"; patch: Partial<Omit<SequenceToken, "type">> }
  | { type: "replace"; tokens: NumberingToken[] }
  | { type: "undo" }
  | { type: "redo" };

export function initialEditorState(tokens: NumberingToken[]): EditorState {
  return {
    items: itemsFromTokens(tokens),
    past: [],
    future: [],
    typingIn: null,
    focusId: null,
  };
}

function commit(state: EditorState, items: EditorItem[]): EditorState {
  return {
    items,
    past: [...state.past, state.items],
    future: [],
    typingIn: null,
    focusId: null,
  };
}

function moveTo(items: EditorItem[], from: number, to: number): EditorItem[] {
  if (from < 0 || to < 0 || from >= items.length || to >= items.length) return items;
  const next = [...items];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case "load":
      return initialEditorState(action.tokens);
    case "insert": {
      if (
        action.token.type === "sequence" &&
        state.items.some((item) => item.token.type === "sequence")
      ) {
        return state;
      }
      const item: EditorItem = { id: newId(), token: action.token };
      const next = commit(state, [...state.items, item]);
      return action.token.type === "text" ? { ...next, focusId: item.id } : next;
    }
    case "label": {
      const items = state.items.map((item) =>
        item.id === action.id && item.token.type === "text"
          ? { ...item, token: { type: "text" as const, value: action.value } }
          : item,
      );
      // Typing in one Label is one undo step, until anything else happens.
      if (state.typingIn === action.id) return { ...state, items, focusId: null };
      return { ...commit(state, items), typingIn: action.id };
    }
    case "prune": {
      // Not a history entry: an empty Label adds nothing to the format, so undo bringing one
      // back is harmless and the next blur removes it again.
      const items = state.items.filter(
        (item) => item.token.type !== "text" || item.token.value !== "",
      );
      return items.length === state.items.length
        ? state
        : { ...state, items, typingIn: null, focusId: null };
    }
    case "remove":
      return commit(
        state,
        state.items.filter((item) => item.id !== action.id),
      );
    case "move": {
      const from = state.items.findIndex((item) => item.id === action.id);
      const items = moveTo(state.items, from, from + action.direction);
      return items === state.items ? state : commit(state, items);
    }
    case "reorder": {
      const ids = state.items.map((item) => item.id);
      const items = moveTo(
        state.items,
        ids.indexOf(action.activeId),
        ids.indexOf(action.overId),
      );
      return items === state.items ? state : commit(state, items);
    }
    case "sequence": {
      const items = state.items.map((item) =>
        item.token.type === "sequence"
          ? { ...item, token: { ...item.token, ...action.patch } }
          : item,
      );
      return commit(state, items);
    }
    case "replace":
      return commit(state, itemsFromTokens(action.tokens));
    case "undo": {
      const previous = state.past[state.past.length - 1];
      if (!previous) return state;
      return {
        items: previous,
        past: state.past.slice(0, -1),
        future: [state.items, ...state.future],
        typingIn: null,
        focusId: null,
      };
    }
    case "redo": {
      const [next, ...rest] = state.future;
      if (!next) return state;
      return {
        items: next,
        past: [...state.past, state.items],
        future: rest,
        typingIn: null,
        focusId: null,
      };
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
