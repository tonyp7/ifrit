import type { ReactNode } from "react";
import { Link } from "react-router";

import { cn } from "@/lib/utils";

// The control in a row's primary cell. Its `::after` covers the whole row (the row must be
// `relative`), so a click anywhere on the row lands on it: to a mouse user the row is
// clickable, while a keyboard or screen-reader user gets a real link or button to Tab to and
// activate, and a link can be opened in a new tab. The row's actions menu and drag handle sit
// above it (`relative z-10`) and keep their own clicks. The focus ring is drawn on the
// pseudo-element so it surrounds the row, not just the text.
const ROW_CONTROL_CLASS =
  "cursor-pointer focus-visible:outline-none after:absolute after:inset-0 focus-visible:after:ring-2 focus-visible:after:ring-inset focus-visible:after:ring-ring";

interface RowControlProps {
  children?: ReactNode;
  /** Names the control when its cell shows no text, or none that says what it opens. */
  "aria-label"?: string;
  className?: string;
}

/** A row that opens a page: a link, so it can be opened in a new tab and its address copied. */
export function RowLink({
  to,
  children,
  className,
  ...rest
}: RowControlProps & { to: string }) {
  return (
    <Link to={to} className={cn(ROW_CONTROL_CLASS, className)} {...rest}>
      {children}
    </Link>
  );
}

/** A row that opens a dialog: there is no address, so a button that looks like the link. */
export function RowButton({
  onClick,
  children,
  className,
  ...rest
}: RowControlProps & { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn("text-left", ROW_CONTROL_CLASS, className)}
      {...rest}
    >
      {children}
    </button>
  );
}
