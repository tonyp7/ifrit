export type Restart = "never" | "yearly" | "monthly" | "daily";

export type NumberingToken =
  | { type: "text"; value: string }
  | { type: "year" }
  | { type: "month" }
  | { type: "day" }
  | { type: "sequence"; digits: number; start_at: number; restart: Restart };

export type SequenceToken = Extract<NumberingToken, { type: "sequence" }>;

/** `GET /api/invoice-numbering`, exactly as the API returns it. */
export interface NumberingState {
  tokens: NumberingToken[];
  /** The sequence value the next invoice issued today would receive. */
  next_value: number;
  /** The next three numbers, rendered for today by the server. */
  preview: string[];
  /** Whether any invoice has been issued (or issued then voided). */
  has_issued: boolean;
}
