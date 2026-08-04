THIS IS A DRAFT - NOT YET REVIEWED AND NOT YET IMPLEMENTED

# Timesheet — User Stories

- The screen where a `consultant` logs time against a `Service Line` they're assigned to (see [project.md](project.md)).
- A `consultant` can **Submit** his weekly/monthly allocation against a service line. In this case it is no longer editable.
- The screen where a `manager` can see his own timesheet, but also those of `consultants`, and **Validate** timesheet submitted or re-open them. This is a separate **Validation** screen, reached via the `timesheet` nav icon's dropdown (manager role only) — see [home.md § Timesheet Menu](home.md#timesheet-menu). The screen's own layout/content is not yet specified (see Open Questions below).

## UI/UX for mobile first timesheet

- Each **service line** is a logical row (shown with its parent project's name for context — a
  consultant assigned to multiple service lines on the same project gets one row per service
  line, never one combined row per project).
- Users can select **Week** or **Month** as the view to submit
- Each **day of the selected month/week** is a logical column.
- A cell = hours logged for a given project service line on a given day.
- One data model drives two responsive views: a day-by-day view on mobile, and a spreadsheet grid on desktop/tablet.
- The UI never shows a 7 days (depending if the user selected Weekly or Monthly) or 30+ column grid on small screens  — instead it shows one day at a time with service lines listed vertically, using the same underlying data.

### State 
State needed at the top level:
- `monthDate` — first-of-month Date representing the active month.
- `serviceLines` — array of `Service Lines`.
- `entries` — `Entries` map.
- `selectedKey` — dayKey of the currently open day (mobile view only).
- Derived, not stored: `days` (all Date objects in the month), day totals, service line totals, month total.

### Derived values
- `dayTotal(dayKey)` — sum of hours across all project service lines for that day.
- `serviceLineTotal(serviceLineId)` — sum of hours across all days in the month for that service line.
- `periodTotal` — sum of all service lines totals for the period (week or month)
- Recompute these live on every keystroke, purely from local `entries` state — see §Persistence
  below for when an edited cell is actually written to the database.

### Persistence

- Each cell autosaves to the `clocking` table on **blur** — not per-keystroke, not on a timer.
  The derived totals above still update live from local state on every keystroke regardless of
  whether the underlying row has been persisted yet.
- On blur, if the value is `0`: no save call is made. If a `clocking` row already exists for that
  `(user, service_line, date)` (the user had a value there earlier and cleared it), it is
  deleted — this is the trigger for §Schema's delete-on-zero rule, restated here since this is
  where it actually fires.
- On blur, if the value is `> 0`: the row is upserted (`INSERT ... ON CONFLICT (user_id,
  service_line_id, date) DO UPDATE`, matching the table's unique constraint) with `status =
  'open'`.
- This flow only ever applies to `open` rows — once a row is `submitted`/`validated` its cell
  renders read-only (see the user stories above), so there's no blur-to-save path to guard
  against separately.

### Shared header (all breakpoints)
- Month label (e.g. "August 2026") OR Week Number (e.g. "Week 34") with prev/next controls.
- Month or Week total hours, right-aligned.
- Changing month/week resets `selectedKey` to today's date if today falls in the new month/week, otherwise to the 1st week of the day/month.

### Mobile view
1. **Day strip**: horizontally scrollable row of day chips, one per day in the month.
   - Each chip shows: weekday abbreviation (3 letters: Mon, Tue, Wed, etc.), day number, total hours logged that day (accross all service lines).
   - Today gets a distinct marker (e.g. small dot).
   - Selected day gets a filled/highlighted state.
   - Tapping a chip sets `selectedKey`.
2. **Selected day detail card**: full date heading + day total, then one row per service line:
   - project name + service line name + numeric hour input (step 0.5, min 0, max 24), autosaved
     on blur (see §Persistence above).
   - "Add service line" affordance at the end of the list — opens the constrained dropdown
     described in §Interactions & validation below, not free text.
   - Empty state message if no service lines are added yet.
3. **Sticky bottom summary bar**: selected day's total and running month-to-date total, always visible while scrolling/typing.

### Desktop / tablet view
- Spreadsheet-style grid/table:
  - Sticky header row: day-of-week 1 letter (M, T, W, etc) + day number per column, weekend columns visually shaded, today's column highlighted (e.g. top border accent).
  - Sticky first column: project name + service line name + color dot + remove-service-line
    control (visible on row hover) — the service line name is required here, not optional
    styling: it's what disambiguates two rows belonging to the same project (see
    [project.md § Service Lines](project.md#service-lines)).
  - Sticky last column: per-row (per-service-line) month total.
  - Bottom total row: per-day totals + grand month total, sticky-left on first cell.
  - Each cell is an input, no visible border until focused, autosaved on blur (see §Persistence
    above).
  - Horizontally scrollable container for months with many days; header/first column/last column stay pinned.
- "Add service line" control below the grid — opens the same constrained dropdown as mobile, not
  free text.

Both views read/write the exact same `entries`/`serviceLines` state, so resizing the viewport
never loses data.

## Interactions & validation

- A week starts on Monday, hardcoded, as per ISO-8601
- Hour input accepts numbers in 0.5 increments, range 0–24; reject/ignore out-of-range or non-numeric input rather than throwing.
- Adding a service line is **not free text** — clicking "Add service line" opens a dropdown
  listing eligible service lines (see constraints below), labeled by their parent project name +
  service line name. Picking one assigns the next color from a fixed rotating palette and appends
  it to `serviceLines`.
- Removing a service line (desktop only, exposed via hover): removes the service line and its
  entries from state.
- No confirmation dialogs for hour edits — this is a live, low-friction data entry surface.
- The "Add service line" dropdown only lists service lines meeting **all** of:
  - the parent project's `status` is `"active"`
  - the parent project's `is_active` is `true`
  - the current user is assigned to that `service_line` (i.e. is one of its consultants)
  - the `service_line`'s `is_active` is `true`

## Schema

`clocking` is the core underlying table from which timesheets are built. An item in `clocking` contains
the following information:
 - `id` PK
 - `user_id` FK → Users 
 - `service_line_id` FK → service_lines
 - `date` date (no time of day) -- The data on which the time was logged
 - `time` time of day (no date) -- The actual timing logged (e.g. 01:00:00 for 1H)
 - `comment` TEXT default NULL -- An optional comment. This is unused in the current UI
 - `last_updated_by` FK → Users -- A timesheet can be manually edited by someone else, this allow potentially tracking of this information
 - `updated_at` timestampz default now()
 - `status` ENUM: open, submitted, validated, default open
(user_id, service_lines, date) -> unique constraint

Implication 1: It is not possible to log two different times against the same project service line for the same user.
This is intended. The design of the model is to remain simple (e.g. on the 8th of August, I spent 3H on project service line X) rather than finely grained (on the 8th of August, I spent 1.5H on project service line X, had a break of 2H then spent another 1.5H on project service line X)

Note: It is useless to have an entry with 0 time in database. So if a user enters 1H, but later reverse to 0, an entry in database
serves no purpose. As a result, 0-entries should not be saved and if an existing entry in db exists it should be deleted.

## Deletion of Services Lines

## Open Questions

- **From [project.md § Service Lines](project.md#service-lines)**: `Service Line` deletion on an `active`
  project is supposed to be blocked once any time has been logged against that line (an orphan
  line with no logged time is safely deletable). That check has nothing to query yet, since no
  time-entry concept is defined here. **TODO once this doc's data model exists**: implement the
  "has this service line got logged time?" check and switch `project.md`'s `active`-project line
  deletion from its current unconditional-allow fallback to the real conditional rule — see
  [project.md § Service Lines](project.md#service-lines) and
  [project.md § Service Line Validation rules](project.md#validation-rules-1).

### Review pass (draft feedback — not yet resolved)

The points below came out of a first review of this draft. Grouped roughly by severity;
addressing the "Critical" ones is a prerequisite for implementation, the rest can probably be
resolved alongside them or deferred.

**Resolved**

- ~~No persistence/sync model.~~ Settled: autosave on blur, skip saving (and delete any existing
  row) when the value is `0`. See the new §Persistence section.
- ~~"Add project" self-contradictory.~~ Settled: it was never free text — it's "Add service
  line," a constrained dropdown. See §Interactions & validation's rewritten constraints.
- ~~Row grain ambiguous between mobile/desktop.~~ Settled as a corollary of the above: the row
  unit is always the service line (shown with its parent project's name for context); the
  desktop sticky first column now includes the service line name too, matching mobile.
- ~~Delete-on-zero rule missing a status guard.~~ Settled: covered by §Persistence — the
  blur-to-save flow only ever runs on `open` rows, since `submitted`/`validated` cells render
  read-only.
- ~~Manager review screen has no entry point.~~ Partially settled: it's a separate screen,
  reached via the `timesheet` nav icon's dropdown for the literal `manager` role only (not
  `administrator`) — "My timesheet" vs. "Validation." See
  [home.md § Timesheet Menu](home.md#timesheet-menu) and
  [user.md § Role → Screen Access](user.md#role--screen-access). **Still open**: the Validation
  screen's own layout/content (this doc's UI/UX section still only covers the single-user
  data-entry grid) — see the Critical item below.

**Critical — blocks implementation as written**

- **Submit/Validate/Re-open have no UI at all, and no defined granularity.** The user stories are
  the only place these three actions are mentioned — no button, control, or screen is described
  anywhere in §UI/UX. Open sub-questions:
  - Does Submit act on one cell, one day, one service line's whole period, or everything visible
    at once?
  - `clocking.status` lives on individual `(user, service_line, date)` rows — can a period be
    *partially* submitted (some days open, some submitted), or must it be atomic? Nothing
    enforces or forbids this today.
  - Does "re-open" mean `submitted → open` only, or also `validated → open`? The enum only has 3
    values, so re-open must collapse into one of these — should be explicit.
  - Can a manager validate their *own* submitted timesheet (self-approval)?
  - Can any manager validate any consultant's timesheet system-wide, or only ones on projects
    they're "responsible for" — a concept `project.md` itself never formalized (no owner/manager
    FK on `Project`)? This doc inherits that same unresolved question.
- **The Validation screen's own layout/content is still unspecified.** It now has a confirmed
  entry point (see the Resolved item above), but §UI/UX still only describes the single-user
  data-entry grid. Half the user stories are about a manager browsing and reviewing *other
  people's* timesheets, and there's no layout, no consultant picker, no read-only-vs-editable
  state description for that screen at all.
- **"Remove service line" looks destructive with no confirmation, conflicting with an
  established app-wide rule.** §Interactions & validation says removing a service line "removes
  the service line and its entries from state." The "no confirmation dialogs" line explicitly
  scopes itself to *hour edits* only — it doesn't say whether removing a service line (potentially
  deleting a whole period's entries, possibly including already-submitted/validated ones) also
  skips confirmation. [frontend.md's Destructive Actions
  convention](../architecture/frontend.md#destructive-actions) requires a confirmation dialog for
  exactly this kind of action app-wide. Also unclear: does "remove" only hide the row from the
  current view, or hard-delete `clocking` rows — including ones a manager already validated?

**Missing constraints**

- **No week-equivalent state.** §State only lists `monthDate`; there's no `weekDate` or
  equivalent, yet Week is a selectable view. An ISO week can span two calendar months — with only
  a month anchored in state, it's unclear how a week view near a month boundary is represented or
  navigated (does prev/next move by week or by month?).
- **Garbled sentence** in §Shared header: "resets `selectedKey` to today's date if today falls in
  the new month/week, otherwise to the 1st week of the day/month." Doesn't parse — needs
  rewriting before it's implementable.
- **`clocking` schema gaps relative to this project's own conventions** (per
  [database.md](../architecture/database.md), every other table follows these):
  - The unique constraint is listed as `(user_id, service_lines, date)` — should be
    `service_line_id`, matching the actual column name above it.
  - No `created_at`, only `updated_at` — every other table in `database.md` has both.
  - PK type isn't stated (presumably UUID like everywhere else, but not said).
  - The UI's 0–24 / 0.5-increment validation has no DB-level `CHECK` — every other bounded value
    in this schema (`status`, `theme_preference`, `uom`, etc.) gets one. Without it, nothing stops
    an out-of-range value arriving via a direct API call or a manager's manual edit.
- **`time TIME` to store a *duration* is an unusual modeling choice.** "01:00:00 for 1H" stores a
  duration in a time-of-day-typed column. Postgres has `INTERVAL` for durations, and the rest of
  the app already uses plain `NUMERIC` for fractional quantities (`Service Line.quantity`). Worth
  confirming this is intentional rather than a modeling shortcut — it works arithmetically up to
  24:00:00, but reads oddly to anyone querying the schema cold.
- **`last_updated_by` implies a capability that's never specified.** The column note says "A
  timesheet can be manually edited by someone else" — but no section describes who can do this (a
  manager? only for their own consultants? only while `status = open`?).

**Edge cases / smaller inconsistencies**

- The `## Deletion of Services Lines` heading directly above has no content at all — looks like
  an unfinished stub rather than a deliberate empty section.
- **Timezone/day-boundary handling** for "today" and the `date` column is unspecified —
  browser-local, server, or a fixed org timezone matters for entries logged near midnight.
- **`comment` field** is defined but flagged unused in the current UI — fine if deliberate
  scope-fencing for a later iteration, just confirm it's not an oversight.
- No cap/overflow behavior stated for a consultant with many assigned service lines across
  projects (mobile vertical list / desktop sticky column) — probably low-risk, but unaddressed.
