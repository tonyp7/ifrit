import { describe, expect, it } from "vitest";

import {
  DEFAULT_TOKENS,
  editorReducer,
  formatErrors,
  formatWarnings,
  initialEditorState,
  itemsFromTokens,
  PRESETS,
  previewStart,
  renderNumber,
  sequenceExample,
  tokensFromItems,
  type EditorAction,
  type EditorState,
} from "@/lib/invoiceNumbering";
import type { NumberingToken } from "@/types/invoiceNumbering";

const OCT_14 = new Date(2026, 9, 14);
const seq = (digits = 4, restart: "never" | "yearly" | "monthly" | "daily" = "yearly") =>
  ({ type: "sequence", digits, start_at: 1, restart }) as const;

function run(state: EditorState, ...actions: EditorAction[]) {
  return actions.reduce(editorReducer, state);
}

const tokens = (state: EditorState) => tokensFromItems(state.items);

describe("rendering", () => {
  it("renders the default format", () => {
    expect(renderNumber(DEFAULT_TOKENS, 1, OCT_14)).toBe("INV-2026-0001");
  });

  it("renders dates and pads the sequence", () => {
    const monthly: NumberingToken[] = [
      { type: "year" },
      { type: "month" },
      { type: "text", value: "-" },
      seq(3, "monthly"),
    ];
    expect(renderNumber(monthly, 1, OCT_14)).toBe("202610-001");
    expect(renderNumber([{ type: "day" }, seq(2, "daily")], 7, OCT_14)).toBe("1407");
  });

  it("writes an overflow in full", () => {
    expect(renderNumber([seq(5, "never")], 100000, OCT_14)).toBe("100000");
  });

  it("shows the presets with today's date", () => {
    expect(PRESETS.map((p) => renderNumber(p.tokens, 1, OCT_14))).toEqual([
      "INV-00001",
      "2026-0001",
      "202610-001",
    ]);
  });

  it("gives a sequence's example values", () => {
    expect(sequenceExample({ ...seq(5, "never") })).toBe("00001, 00002, 00003, ...");
  });
});

describe("validation", () => {
  it("requires a sequence", () => {
    expect(formatErrors([{ type: "text", value: "INV-" }, { type: "year" }])).toEqual([
      "no_sequence",
    ]);
  });

  it("refuses characters other than letters, digits, - / _", () => {
    expect(formatErrors([{ type: "text", value: "INV#" }, seq()])).toEqual(["bad_text"]);
  });

  it("caps the longest number at 100 characters", () => {
    expect(formatErrors([{ type: "text", value: "x".repeat(90) }, seq(10)])).toEqual([]);
    expect(formatErrors([{ type: "text", value: "x".repeat(91) }, seq(10)])).toEqual([
      "too_long",
    ]);
  });

  it("warns when a counter restarts without its own date tiles", () => {
    expect(
      formatWarnings([{ type: "text", value: "INV-" }, { type: "year" }, seq(4, "monthly")]),
    ).toEqual(["monthly_repeats"]);
    expect(formatWarnings([{ type: "year" }, { type: "month" }, seq(4, "monthly")])).toEqual(
      [],
    );
    expect(formatWarnings([seq(4, "yearly")])).toEqual(["yearly_repeats"]);
    expect(formatWarnings([{ type: "year" }, { type: "month" }, seq(4, "daily")])).toEqual([
      "daily_repeats",
    ]);
    expect(formatWarnings([seq(4, "never")])).toEqual([]);
  });

  it("re-evaluates when the restart changes", () => {
    const state = run(initialEditorState([{ type: "year" }, seq(4, "monthly")]), {
      type: "sequence",
      patch: { restart: "yearly" },
    });
    expect(formatWarnings(tokens(state))).toEqual([]);
  });
});

const label = (value: string) => ({ type: "text", value }) as const;
const ids = (state: EditorState) => state.items.map((item) => item.id);
const kinds = (state: EditorState) => state.items.map((item) => item.token.type);

describe("items and tokens", () => {
  it("makes one chip per token, Labels included", () => {
    const items = itemsFromTokens(DEFAULT_TOKENS);
    expect(items.map((i) => i.token.type)).toEqual(["text", "year", "text", "sequence"]);
    expect(new Set(items.map((i) => i.id)).size).toBe(4);
  });

  it("round-trips the default format", () => {
    expect(tokensFromItems(itemsFromTokens(DEFAULT_TOKENS))).toEqual(DEFAULT_TOKENS);
  });

  it("joins neighbouring Labels and drops empty ones when saving", () => {
    const items = itemsFromTokens([
      label("INV"),
      label(""),
      label("-"),
      { type: "year" },
      label(""),
      seq(),
    ]);
    expect(tokensFromItems(items)).toEqual([label("INV-"), { type: "year" }, seq()]);
  });

  it("loads a preset's text as Label chips", () => {
    expect(kinds(initialEditorState(PRESETS[0].tokens))).toEqual(["text", "sequence"]);
  });
});

describe("editing", () => {
  it("appends a tile at the end", () => {
    const state = run(initialEditorState([label("INV-"), seq()]), {
      type: "insert",
      token: { type: "year" },
    });
    expect(tokens(state)).toEqual([label("INV-"), seq(), { type: "year" }]);
  });

  it("adds an empty Label at the end and asks for its focus", () => {
    const state = run(initialEditorState([seq()]), { type: "insert", token: label("") });
    expect(kinds(state)).toEqual(["sequence", "text"]);
    expect(state.focusId).toBe(state.items[1].id);
    expect(tokens(state)).toEqual([seq()]);
  });

  it("allows several Labels", () => {
    let state = initialEditorState([seq()]);
    state = run(
      state,
      { type: "insert", token: label("") },
      { type: "insert", token: label("") },
    );
    expect(kinds(state)).toEqual(["sequence", "text", "text"]);
  });

  it("refuses a second sequence", () => {
    const state = initialEditorState([seq()]);
    expect(run(state, { type: "insert", token: seq() })).toBe(state);
  });

  it("edits a Label's text", () => {
    let state = run(initialEditorState([seq()]), { type: "insert", token: label("") });
    state = run(state, { type: "label", id: state.items[1].id, value: "INV-" });
    expect(tokens(state)).toEqual([seq(), label("INV-")]);
    expect(state.focusId).toBeNull();
  });

  it("removes a chip, a Label too", () => {
    let state = initialEditorState([label("INV-"), { type: "year" }, seq()]);
    state = run(state, { type: "remove", id: state.items[0].id });
    expect(tokens(state)).toEqual([{ type: "year" }, seq()]);
  });

  it("drops empty Labels on prune, without a history entry", () => {
    let state = run(initialEditorState([seq()]), { type: "insert", token: label("") });
    const past = state.past.length;
    state = run(state, { type: "prune" });
    expect(kinds(state)).toEqual(["sequence"]);
    expect(state.past).toHaveLength(past);
  });

  it("leaves Labels with text alone on prune", () => {
    const state = initialEditorState([label("INV-"), seq()]);
    expect(run(state, { type: "prune" })).toBe(state);
  });

  it("moves a chip left and right", () => {
    let state = initialEditorState([{ type: "year" }, { type: "month" }, seq()]);
    const year = state.items[0];
    state = run(state, { type: "move", id: year.id, direction: 1 });
    expect(tokens(state).map((t) => t.type)).toEqual(["month", "year", "sequence"]);
    state = run(state, { type: "move", id: year.id, direction: -1 });
    expect(tokens(state).map((t) => t.type)).toEqual(["year", "month", "sequence"]);
  });

  it("does not move past either end", () => {
    const state = initialEditorState([{ type: "year" }, seq()]);
    expect(run(state, { type: "move", id: state.items[0].id, direction: -1 })).toBe(state);
    expect(run(state, { type: "move", id: state.items[1].id, direction: 1 })).toBe(state);
  });

  it("moves and reorders a Label like any chip, keeping its text", () => {
    let state = initialEditorState([label("INV-"), seq()]);
    const [text, sequence] = ids(state);
    state = run(state, { type: "reorder", activeId: text, overId: sequence });
    expect(tokens(state)).toEqual([seq(), label("INV-")]);
    state = run(state, { type: "move", id: text, direction: -1 });
    expect(tokens(state)).toEqual([label("INV-"), seq()]);
  });

  it("allows two adjacent separators once a chip between them goes", () => {
    let state = initialEditorState([label("-"), { type: "year" }, label("-"), seq()]);
    state = run(state, { type: "remove", id: state.items[1].id });
    // Two Labels side by side in the editor, one text once saved.
    expect(kinds(state)).toEqual(["text", "text", "sequence"]);
    expect(tokens(state)).toEqual([label("--"), seq()]);
    expect(renderNumber(tokens(state), 1, OCT_14)).toBe("--0001");
  });

  it("changes the sequence's settings", () => {
    const state = run(initialEditorState([seq()]), { type: "sequence", patch: { digits: 6 } });
    expect(tokens(state)).toEqual([seq(6)]);
  });
});

describe("undo and redo", () => {
  it("undoes a preset and redoes it", () => {
    let state = initialEditorState(DEFAULT_TOKENS);
    state = run(state, { type: "replace", tokens: PRESETS[0].tokens });
    state = run(state, { type: "undo" });
    expect(tokens(state)).toEqual(DEFAULT_TOKENS);
    state = run(state, { type: "redo" });
    expect(tokens(state)).toEqual(PRESETS[0].tokens);
  });

  it("gathers typing in one Label into one step", () => {
    let state = run(initialEditorState([seq()]), { type: "insert", token: label("") });
    const id = state.items[1].id;
    const before = state.past.length;
    state = run(
      state,
      { type: "label", id, value: "I" },
      { type: "label", id, value: "IN" },
      { type: "label", id, value: "INV" },
    );
    expect(state.past).toHaveLength(before + 1);
    state = run(state, { type: "undo" });
    expect(tokens(state)).toEqual([seq()]);
  });

  it("starts a new step after another action", () => {
    let state = run(initialEditorState([seq()]), { type: "insert", token: label("") });
    const id = state.items[1].id;
    state = run(
      state,
      { type: "label", id, value: "A" },
      { type: "insert", token: { type: "year" } },
      { type: "label", id, value: "AB" },
    );
    state = run(state, { type: "undo" });
    // Only the "B" is undone: "A" and the Year chip were separate steps.
    expect(tokens(state)).toContainEqual(label("A"));
    expect(tokens(state)).toContainEqual({ type: "year" });
  });

  it("starts a new step for a different Label", () => {
    let state = initialEditorState([seq()]);
    state = run(
      state,
      { type: "insert", token: label("") },
      { type: "insert", token: label("") },
    );
    const [, a, b] = ids(state);
    const before = state.past.length;
    state = run(
      state,
      { type: "label", id: a, value: "X" },
      { type: "label", id: b, value: "Y" },
    );
    expect(state.past).toHaveLength(before + 2);
  });

  it("puts the default format back with a reset", () => {
    let state = initialEditorState([seq()]);
    state = run(state, { type: "replace", tokens: DEFAULT_TOKENS });
    expect(tokens(state)).toEqual(DEFAULT_TOKENS);
  });
});

describe("previewStart", () => {
  it("uses the server's next value while the restart is unchanged", () => {
    expect(previewStart(DEFAULT_TOKENS, [{ type: "text", value: "X" }, seq()], 43)).toEqual({
      value: 43,
      fresh: false,
    });
  });

  it("starts fresh when the restart changes", () => {
    expect(previewStart(DEFAULT_TOKENS, [{ ...seq(4, "monthly"), start_at: 5 }], 43)).toEqual({
      value: 5,
      fresh: true,
    });
  });
});
