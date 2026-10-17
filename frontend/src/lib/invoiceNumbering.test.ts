import { describe, expect, it } from "vitest";

import {
  DEFAULT_TOKENS,
  editorReducer,
  formatErrors,
  formatWarnings,
  initialEditorState,
  itemsFromTokens,
  movableIds,
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
    const monthly: NumberingToken[] = [{ type: "year" }, { type: "month" }, { type: "text", value: "-" }, seq(3, "monthly")];
    expect(renderNumber(monthly, 1, OCT_14)).toBe("202610-001");
    expect(renderNumber([{ type: "day" }, seq(2, "daily")], 7, OCT_14)).toBe("1407");
  });

  it("writes an overflow in full", () => {
    expect(renderNumber([seq(5, "never")], 100000, OCT_14)).toBe("100000");
  });

  it("shows the presets with today's date", () => {
    expect(PRESETS.map((p) => renderNumber(p.tokens, 1, OCT_14))).toEqual(["INV-00001", "2026-0001", "202610-001"]);
  });

  it("gives a sequence's example values", () => {
    expect(sequenceExample({ ...seq(5, "never") })).toBe("00001, 00002, 00003, ...");
  });
});

describe("validation", () => {
  it("requires a sequence", () => {
    expect(formatErrors([{ type: "text", value: "INV-" }, { type: "year" }])).toEqual(["no_sequence"]);
  });

  it("refuses characters other than letters, digits, - / _", () => {
    expect(formatErrors([{ type: "text", value: "INV#" }, seq()])).toEqual(["bad_text"]);
  });

  it("caps the longest number at 100 characters", () => {
    expect(formatErrors([{ type: "text", value: "x".repeat(90) }, seq(10)])).toEqual([]);
    expect(formatErrors([{ type: "text", value: "x".repeat(91) }, seq(10)])).toEqual(["too_long"]);
  });

  it("warns when a counter restarts without its own date tiles", () => {
    expect(formatWarnings([{ type: "text", value: "INV-" }, { type: "year" }, seq(4, "monthly")])).toEqual(["monthly_repeats"]);
    expect(formatWarnings([{ type: "year" }, { type: "month" }, seq(4, "monthly")])).toEqual([]);
    expect(formatWarnings([seq(4, "yearly")])).toEqual(["yearly_repeats"]);
    expect(formatWarnings([{ type: "year" }, { type: "month" }, seq(4, "daily")])).toEqual(["daily_repeats"]);
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

describe("slots and tokens", () => {
  it("alternates text slots and chips, with slots at both ends", () => {
    const items = itemsFromTokens([{ type: "year" }, { type: "month" }]);
    expect(items.map((i) => i.kind)).toEqual(["text", "chip", "text", "chip", "text"]);
    expect(tokensFromItems(items)).toEqual([{ type: "year" }, { type: "month" }]);
  });

  it("round-trips the default format", () => {
    expect(tokensFromItems(itemsFromTokens(DEFAULT_TOKENS))).toEqual(DEFAULT_TOKENS);
  });
});

describe("editing", () => {
  it("inserts a tile at the caret, splitting the slot", () => {
    let state = initialEditorState([{ type: "text", value: "INV-" }, seq()]);
    const slot = state.items[0];
    state = run(state, { type: "focus", caret: { slotId: slot.id, offset: 4 } }, { type: "insert", token: { type: "year" } });
    expect(tokens(state)).toEqual([{ type: "text", value: "INV-" }, { type: "year" }, seq()]);
  });

  it("splits text in the middle", () => {
    let state = initialEditorState([{ type: "text", value: "AB" }, seq()]);
    state = run(state, { type: "focus", caret: { slotId: state.items[0].id, offset: 1 } }, { type: "insert", token: { type: "day" } });
    expect(tokens(state)).toEqual([{ type: "text", value: "A" }, { type: "day" }, { type: "text", value: "B" }, seq()]);
  });

  it("appends a tile when nothing is focused", () => {
    const state = run(initialEditorState([seq()]), { type: "insert", token: { type: "year" } });
    expect(tokens(state)).toEqual([seq(), { type: "year" }]);
  });

  it("refuses a second sequence", () => {
    const state = initialEditorState([seq()]);
    expect(run(state, { type: "insert", token: seq() })).toBe(state);
  });

  it("removes a whole chip with Backspace at the start of the next slot", () => {
    let state = initialEditorState([{ type: "text", value: "A" }, { type: "year" }, { type: "text", value: "B" }, seq()]);
    const afterYear = state.items[2];
    state = run(state, { type: "backspace", slotId: afterYear.id });
    expect(tokens(state)).toEqual([{ type: "text", value: "AB" }, seq()]);
    expect(state.caret?.offset).toBe(1);
  });

  it("moves a chip left and right", () => {
    let state = initialEditorState([{ type: "year" }, { type: "month" }, seq()]);
    const year = state.items.find((i) => i.kind === "chip" && i.token.type === "year")!;
    state = run(state, { type: "move", id: year.id, direction: 1 });
    expect(tokens(state).map((t) => t.type)).toEqual(["month", "year", "sequence"]);
    state = run(state, { type: "move", id: year.id, direction: -1 });
    expect(tokens(state).map((t) => t.type)).toEqual(["year", "month", "sequence"]);
  });

  it("reorders by drag, texts included", () => {
    let state = initialEditorState([{ type: "text", value: "INV-" }, seq()]);
    const [text, sequence] = movableIds(state.items);
    state = run(state, { type: "reorder", activeId: text, overId: sequence });
    expect(tokens(state)).toEqual([seq(), { type: "text", value: "INV-" }]);
  });

  it("allows two adjacent separators once a chip between them goes", () => {
    let state = initialEditorState([{ type: "text", value: "-" }, { type: "year" }, { type: "text", value: "-" }, seq()]);
    const year = state.items.find((i) => i.kind === "chip" && i.token.type === "year")!;
    state = run(state, { type: "remove", id: year.id });
    expect(renderNumber(tokens(state), 1, OCT_14)).toBe("--0001");
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

  it("gathers typing in one slot into one step", () => {
    let state = initialEditorState([seq()]);
    const slot = state.items[0];
    state = run(
      state,
      { type: "type", slotId: slot.id, value: "I", offset: 1 },
      { type: "type", slotId: slot.id, value: "IN", offset: 2 },
      { type: "type", slotId: slot.id, value: "INV", offset: 3 },
    );
    expect(state.past).toHaveLength(1);
    state = run(state, { type: "undo" });
    expect(tokens(state)).toEqual([seq()]);
  });

  it("starts a new step after focus leaves the slot", () => {
    let state = initialEditorState([seq()]);
    const slot = state.items[0];
    state = run(
      state,
      { type: "type", slotId: slot.id, value: "A", offset: 1 },
      { type: "focus", caret: null },
      { type: "type", slotId: slot.id, value: "AB", offset: 2 },
    );
    expect(state.past).toHaveLength(2);
  });
});

describe("previewStart", () => {
  it("uses the server's next value while the restart is unchanged", () => {
    expect(previewStart(DEFAULT_TOKENS, [{ type: "text", value: "X" }, seq()], 43)).toEqual({ value: 43, fresh: false });
  });

  it("starts fresh when the restart changes", () => {
    expect(previewStart(DEFAULT_TOKENS, [{ ...seq(4, "monthly"), start_at: 5 }], 43)).toEqual({ value: 5, fresh: true });
  });
});
