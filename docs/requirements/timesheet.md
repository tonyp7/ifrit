THIS IS A DRAFT - NOT YET REVIEWED AND NOT YET IMPLEMENTED

# Timesheet — User Stories

Two distinct screens live under this doc, both reached via the `timesheet` nav icon — see
[home.md § Timesheet Menu](home.md#timesheet-menu) for how the icon's behavior branches by role.
They're kept clearly separate below: one is the data-entry mechanism, the other is the
`project_manager`-only review workflow built on top of it.

- **My Timesheet** (see §My Timesheet (Clocking) below) — where a user logs their own time
  against a `Service Line` they're assigned to (see [project.md](project.md)). Cells are freely
  editable — **there is no Submit step** — until a `project_manager` locks them via §Validation.
- **Validation** (see §Validation below — **placeholder only, not yet specified**) — where a
  `project_manager` sees their own timesheet, but also those of consultants **on projects they're
  assigned to as project manager** (see [user.md § Entity](user.md#entity) for the
  `project_admin`/`project_manager` split — this was gated by a single `manager` role before that
  split), and **locks**/**unlocks** cells to freeze/unfreeze them from further edits.

## My Timesheet (Clocking)

The screen where a user enters their own time. This section covers the data-entry mechanism
only — see §Validation below for the separate `project_manager`-facing lock/unlock screen.

- Each **service line** is a logical row (shown with its parent project's name for context — a
  consultant assigned to multiple service lines on the same project gets one row per service
  line, never one combined row per project).
- Users can select **Week** or **Month** as the view. The default `periodType` on first landing
  on the screen depends on breakpoint, not a single fixed default for everyone: **Week** on
  mobile, **Month** on desktop/tablet — matching the same `md:` breakpoint that decides which of
  §Mobile view/§Desktop / tablet view is shown (see below). Rationale: a day-by-day mobile screen
  has no room to usefully show a whole month at once, so Week is the sensible starting point
  there, while the desktop grid has the width to show a full month up front, which is more useful
  as a landing view than a single week. This is a one-time default computed when the screen
  mounts, not a live-synced setting — resizing an already-open tab doesn't force a switch, and
  manually picking the other view is unaffected by this default.
- Each **day of the selected month/week** is a logical column.
- A cell = hours logged for a given project service line on a given day.
- "Today," day boundaries, and which `date` a near-midnight entry lands on are all computed from
  the user's own browser/OS timezone — not server time, not a fixed org timezone.
- One data model drives two responsive views: a day-by-day view on mobile, and a spreadsheet grid on desktop/tablet.
- The UI never shows a 7 days (depending if the user selected Weekly or Monthly) or 30+ column grid on small screens  — instead it shows one day at a time with service lines listed vertically, using the same underlying data.

### State 
State needed at the top level:
- `periodType` — `'week' | 'month'`, which view the user currently has selected (see §Shared
  header below).
- `periodDate` — a single anchor date whose *meaning* depends on `periodType`: the first-of-month
  Date when `periodType === 'month'`, or the Monday of the active week when `periodType ===
  'week'`. One field instead of separate `monthDate`/`weekDate` fields, since exactly one of them
  is ever meaningful at a time — which one just depends on `periodType`.
- `serviceLines` — array of `Service Lines` shown for the *currently displayed period only*.
  Populated from the union of: (1) service lines added via "Add service line" (see
  §Interactions & Input Rules below — assignment-gated) **while this period is the one being
  viewed**, and (2) service lines with *any* existing `time_entries` row for this user in this
  period's date range, regardless of current assignment. (2) is what keeps historical (including
  locked) time visible even after the user is later unassigned from that line.

  **Deliberately not persisted across periods — simple by design, not an oversight**: there is
  no session-wide "added" or "removed" memory. Switching `periodType`/`periodDate` re-derives
  this union from scratch every time: (1) resets to empty (a line added while looking at August
  is not still "added" once you're looking at September — add it again there if you want to log
  time against it), and (2) is refetched for the new period's date range. The rule is simply:
  *a line with data for the period being viewed shows; a line with none doesn't* — whether or
  not it was ever manually added or removed, in this period or any other. An earlier design kept
  "added"/"removed" as session-wide state that had to be reconciled against per-period data on
  every render (e.g. "a line marked removed must still show if it turns out to have data") —
  that reconciliation was a real source of bugs (a just-cleared line staying stuck on screen, a
  manually-added line following the user into unrelated periods with nothing in them) and added
  no capability an end user actually wanted; dropping the cross-period memory entirely removes
  the bug class along with the state that caused it, not just the specific bugs found. See
  §Interactions & Input Rules' "Removing a service line" below for how this makes removal fully
  describable in three branches with no separate suppression state needed.

  **Row order is always ascending by project name, then service line name** — a stable,
  identity-based sort applied to the whole union after merging, not the order lines happened to
  be added/discovered in. This is deliberate: an earlier draft left row order as an accidental
  side effect of fetch order (e.g. whichever line's earliest `time_entries` row fell first within
  the currently-loaded date range), which meant Week and Month could show the same lines in
  different orders since they load different date windows — the two views must show identical
  ordering for the same underlying data, never something that depends on which view happens to
  be open.
- `entries` — `Entries` map.
- `selectedKey` — dayKey of the currently open/focused day. Drives the mobile day
  strip's highlighted chip (see §Mobile view), but isn't mobile-only in what *sets*
  it: the desktop/tablet grid also updates it, on focusing any cell — see §Shared
  header below for why this matters (it's what a `periodType` switch anchors on).
- Derived, not stored: `days` (all Date objects in the active period — 7 for `week`, 28–31 for
  `month`), day totals, service line totals, period total.

### Derived values
- `dayTotal(dayKey)` — sum of hours across all project service lines for that day.
- `serviceLineTotal(serviceLineId)` — sum of hours across all days in the month for that service line.
- `periodTotal` — sum of all service lines totals for the period (week or month)
- Recompute these live on every keystroke, purely from local `entries` state — see §Persistence
  below for when an edited cell is actually written to the database.

### Persistence

- Each cell autosaves to the `time_entries` table on **blur** — not per-keystroke, not on a timer.
  The derived totals above still update live from local state on every keystroke regardless of
  whether the underlying row has been persisted yet.
- On blur, if the value is `0`: no save call is made. If a `time_entries` row already exists for that
  `(user, service_line, date)`, it is deleted. A `0` entry has no reason to exist as a row once
  there's no Submit step for it to matter to — this is simpler than the earlier draft, which
  briefly required saving `0` rows for a since-removed Submit mechanism to attach status to. The
  one place this simplicity has a real cost is deferred to §Validation: locking a date range that
  includes untouched (rowless) days now has to decide what happens to those gaps — see the new
  open question there.
- On blur, if the value is `> 0`: the row is upserted (`INSERT ... ON CONFLICT (user_id,
  service_line_id, date) DO UPDATE`, matching the table's unique constraint) with `is_locked =
  false`. A row created this way is always unlocked by construction — the consultant's own save
  path can never set `is_locked = true`; only a `project_manager`'s action on §Validation can.
- This flow only ever applies while `is_locked = false` — once a row is locked its cell renders
  read-only (see the user stories above), so there's no blur-to-save path to guard against
  separately.
- **Saving a new entry against a service line the user is no longer assigned to must error, not
  silently succeed.** This only affects genuinely new/unlocked entries — a service line can still
  be visible with existing locked rows after unassignment (see §State's population rule and
  §Interactions & Input Rules' removal rule), and those stay untouched and read-only regardless.
  Whether the UI proactively disables such a cell rather than letting the user type into it and
  fail on blur is not yet specified.

#### API contract: `PUT /time-entries` is bulk, not single-entry

**Revised** — resolving the "Bulk-clear mechanism is unspecified" and "backend doesn't enforce
the lock" points from an earlier review pass (see §Open Questions' change history below). The
request body is a **JSON array** of `TimeEntryUpsert` items (`service_line_id`, `date`, `hours`),
length 1 or more — never a bare single object. A normal cell blur (see above) sends a
**one-element array**; removing a service line with logged time in the current period (see
§Interactions & Input Rules' "Removing a service line") sends **one array covering every day
being cleared in the period**, in a single request — never one request per day.

- **Each item is processed and persisted independently** — this is not an all-or-nothing
  transaction across the array. One item failing (see below) never rolls back or blocks any other
  item in the same request.
- **Every item is checked against `is_locked` before being applied, regardless of direction**:
  attempting to delete (`hours == 0`) or overwrite (`hours > 0`) a row where `is_locked = true` is
  rejected for that item — locked rows are fully immutable through this endpoint, full stop.
  Unlocking is exclusively `project_manager`'s domain via §Validation (a different, not-yet-built
  mechanism entirely) — this endpoint never grants that authority to anyone, including the
  original consultant. This closes the gap an earlier review pass found: the lock check used to
  exist only in the frontend (a disabled input), not the backend, so a direct API call could
  delete a locked entry; it's now enforced server-side, unconditionally, on every item.
- Eligibility (`hours > 0` against a service line the user isn't currently assigned to — the
  existing rule above) is likewise checked **per item**, not once for the whole request.
- **Response is also a JSON array**, one result per request item (same order), each reporting its
  own outcome:
  - **Succeeded** — the resulting `TimeEntryOut` (for `hours > 0`) or `null` (for a successful
    `hours == 0` delete), same shape §Data Model already defines.
  - **Rejected** — an error indicator plus a human-readable reason (`"locked"` — the row is
    locked; `"not_eligible"` — see the existing eligibility rule above).
- **Status code**: `200` only if **every** item succeeded. `207 Multi-Status` if **any** item was
  rejected — whether that's 1 of 30 or all 30 — since the response array already carries the
  per-item detail a client needs; there's no separate all-failed status. This replaces the
  existing single-item endpoint's behavior of throwing a `422` for an ineligible save — that's
  now just one rejected item in an always-array response, even for a length-1 array.
- **Frontend handling of a `207`** (relevant to both a single cell and the bulk clear-on-remove
  flow): apply every succeeded item's result to local `entries` state as normal; surface an error
  for the rejected item(s) (e.g. a toast). Specifically for the clear-on-remove flow: if **any**
  item in that request came back rejected (most plausibly a day that got locked by a
  `project_manager` in the moment between opening the confirmation dialog and clicking Confirm —
  see the "race" point below), the service line must **not** be removed from `serviceLines` — it
  now has at least one locked entry in the current period, which §Interactions & Input Rules'
  removal rule already says makes a line non-removable. The line stays visible, showing whatever
  mix of now-cleared and still-locked cells the response actually produced, and the error
  surfaces why the clear was incomplete.
- A practical upper bound on array length isn't specified here (Month view tops out around 31
  items from the clear-on-remove flow) — presumably fine unbounded at this scale, but worth a
  sanity-check limit at implementation time defending against a malformed/abusive request rather
  than trusting the frontend's own bounds.

### Shared header (all breakpoints)
- Option to switch `periodType` between Month view or Week view.
- Month label (e.g. "August 2026") OR Week Number (e.g. "Week 34") with prev/next controls —
  whichever matches the current `periodType`.
- Period total hours (month or week, matching `periodType`), right-aligned.
- Changing `periodDate` via **prev/next** (same `periodType`, moving the window forward/back)
  sets `selectedKey` to the logical step — there's no single "day in focus" driving prev/next,
  so it lands on the new period's boundary closest to where you came from:
  - Example 1. Advancing from Week 34 to Week 35 sets `selectedKey` to Monday of Week 35 (the
    new period's first day, since you moved forward).
  - Example 2. Going back from August 2026 to July 2026 sets `selectedKey` to July 31st (the new
    period's last day, since you moved backward).
- **Switching `periodType`** (Week ↔ Month) is different: it must re-anchor on whichever day
  the user is actually looking at, not jump to an artificial boundary. Concretely: `periodDate`
  is recomputed from the *existing* `selectedKey` (`startOfWeekMonday`/`startOfMonth` of it), not
  reset — so `selectedKey` has to already hold the day currently in focus for this to work.
  `selectedKey` being mobile-only (see §State) was exactly the bug here: the desktop/tablet grid
  never updated it, so it stayed stuck at whatever the last `periodType` switch had set it to
  (typically the 1st of the month) — switching Month → Week would silently anchor on that stale
  day instead of whatever cell the user had actually clicked into. Fixed by having the desktop
  grid update `selectedKey` on focusing any cell, the same way the mobile day strip already does
  on tapping a chip (see §Mobile view) — both views now keep one shared "day in focus," so
  switching `periodType` reliably shows the week/month containing whatever day you were just
  looking at, on either breakpoint.

### Mobile view
1. **Day strip**: horizontally scrollable row of day chips, one per day in the month.
   - Each chip shows: weekday abbreviation (3 letters: Mon, Tue, Wed, etc.), day number, total hours logged that day (accross all service lines).
   - Today gets a distinct marker (e.g. small dot).
   - Selected day gets a filled/highlighted state.
   - Tapping a chip sets `selectedKey`.
2. **Selected day detail card**: full date heading + day total, then one row per service line:
   - project name + service line name + numeric hour input (step 0.5, min 0, max 24), autosaved
     on blur (see §Persistence above), + a remove icon (always visible, not gated behind a
     gesture) — see §Interactions & Input Rules below for when it's actually enabled.
   - "Add service line" affordance at the end of the list — opens the constrained dropdown
     described in §Interactions & Input Rules below, not free text.
   - Empty state message if no service lines are added yet.
3. **Sticky bottom summary bar**: selected day's total and running month-to-date total, always visible while scrolling/typing.

### Desktop / tablet view
- Spreadsheet-style grid/table:
  - Sticky header row: day-of-week label + day number per column, weekend columns visually
    shaded, today's column highlighted (e.g. top border accent). The label itself depends on
    `periodType`: **Week** view (7 columns, room to spare) shows a 3-letter abbreviation (Mon,
    Tue, Wed, ...); **Month** view (28-31 columns, cramped) shows a single letter (M, T, W, ...)
    instead. Both are locale-aware, not hardcoded English strings — same as the mobile day
    strip's weekday abbreviation.
  - Sticky first column: project name + service line name + remove-service-line control — always
    visible, same as mobile, not gated behind row hover (see §Interactions & Input Rules below)
    — the service line name is required here, not optional styling: it's what disambiguates two
    rows belonging to the same project (see [project.md § Service Lines](project.md#service-lines)).
  - Sticky last column: per-row (per-service-line) month/week total.
  - Bottom total row: per-day totals + grand month total, sticky-left on first cell.
  - Each cell is an input, no visible border until focused, autosaved on blur (see §Persistence
    above).
  - Horizontally scrollable container for months with many days; header/first column/last column stay pinned.
- "Add service line" control below the grid — opens the same constrained dropdown as mobile, not
  free text.

Both views read/write the exact same `entries`/`serviceLines` state, so resizing the viewport
never loses data.

Both views have clean UI feedback on the cell's editability — just two states now:
 - Open (`is_locked = false`): standard, editable.
 - Locked (`is_locked = true`): read-only, greyed out.

### Interactions & Input Rules

- A week starts on Monday, hardcoded, as per ISO-8601
- Hour input accepts numbers in 0.5 increments, range 0–24; reject/ignore out-of-range or non-numeric input rather than throwing.
- Adding a service line is **not free text** — clicking "Add service line" opens a dropdown
  listing eligible service lines (see constraints below), labeled by their parent project name +
  service line name. Picking one assigns the next color from a fixed rotating palette and appends
  it to `serviceLines`.
- Removing a service line: an icon on the row, **always visible on both mobile and desktop** —
  not gated behind desktop-only hover or a mobile-only gesture (swipe/long-press). Unifying on an
  always-visible control avoids needing two different reveal mechanisms per breakpoint, and
  matches this app's existing row-action style rather than a hover-only pattern that has no touch
  equivalent.

  **Revised — no longer unconditionally non-destructive.** The earlier design ("remove" only ever
  touches the view, `time_entries` rows are never touched) let a user re-add the same line via
  "Add service line" and get their old values back — which felt like an undo, but actually meant
  "remove" never hid anything the user had entered; it just made adding/removing service lines
  from the view a costless, reversible way to declutter a timesheet with many assigned-but-
  currently-unused projects. That's the intended use case (see the top of this doc), but the
  *actual* behavior — silently preserving every value, forever, behind an innocuous-looking "×" —
  isn't honest about what's about to happen when a line **does** have real logged time. Removing a
  service line now branches three ways, based on the currently-displayed period only (i.e. exactly
  the `days` in view — Week or Month, whichever the user currently has selected; a period with no
  logged time for this line is unaffected regardless of what's logged for it in other periods):

  1. **No logged time for this line, this period** (no `entries` key for any day in `days`): the
     line can only be visible in the first place because it was added via "Add service line"
     while viewing this period (see §State above) — removing it here just takes it back out of
     that per-period "added" set, no server call, no dialog. Purely undoing an add; re-adding
     retrieves whatever already exists (nothing was ever at risk, since there was nothing to lose
     for this period).
  2. **Logged (unlocked) time exists for this line, this period**: a confirmation dialog (shadcn/ui
     `AlertDialog`, matching every other destructive action in this app — see
     [frontend.md § Destructive Actions](../architecture/frontend.md#destructive-actions)) —

     > This will delete any time logged for this service line for the period **{{period}}**. Are
     > you sure you want to proceed?

     `{{period}}` is the same label the Shared Header already shows for the current view — e.g.
     "August 2026" for Month, "Week 34" for Week (see §Shared header above) — so the dialog always
     names exactly the range that's about to be affected.
     - **Cancel**: no action; the row, its values, and its lock states (there are none, by
       construction of this branch) are untouched.
     - **Confirm** (destructive-styled, matching every other confirm action in this app): every day
       in the current period's `days` with logged time for this line is cleared in **one bulk `PUT
       /time-entries` call** — one array item (`hours: 0`) per day being cleared, not one request
       per day (see §Persistence's API contract above). If the response is a plain `200`, every
       item cleared and the line is removed from `serviceLines` (also out of this period's "added"
       set, if it happened to be there too — e.g. added this period, then given data, then
       removed); re-adding the same line afterward does **not** restore these values — they're
       actually gone, which is the whole point of warning first. If the response is a `207` (at
       least one day was rejected — in practice, a
       day someone locked in the moment between opening this dialog and clicking Confirm), the
       succeeded days are still cleared, but the line is **not** removed from view (branch 3 below
       now applies to it, since it has a locked entry in this period) — the user sees an error
       explaining the clear was incomplete and why. Time logged for this same line in a *different*
       period (not currently in view) is never touched by this action either way.
  3. **Any locked entry exists for this line, this period**: removal is **blocked entirely** — the
     icon renders disabled (with a tooltip explaining why), and clicking it does nothing. There is
     no partial removal that clears only the unlocked days and leaves the locked ones; a single
     locked day anywhere in the current period's `days` for this line disables the control for the
     *whole* line, for that period. This is intentional, not a limitation to fix later: once a
     `project_manager` has locked any part of a period, a consultant must not be able to make that
     service line disappear from their own timesheet — see §State's population rule above, which
     already guarantees a line with any existing `time_entries` row (locked or not) always
     reappears regardless of assignment/add state; blocking removal here is just making the
     control honest about a case that population rule already made unavoidable.

  In every case, "removed from view" itself (branch 1, and the tail end of a fully-succeeded
  branch 2) is **not persisted anywhere** — it's not even session-wide, let alone saved server
  state; it only ever reflects §State's per-period union at the moment you're looking at it (see
  §State above). Switching periods, or reloading, re-derives visibility from scratch every time.
  Branch 2's data deletion is the one genuinely persisted effect here (that's the point of
  warning about it) — everything else described in this section is just this period's transient
  view of already-persisted (or, for branch 1, never-persisted) data.
- No confirmation dialogs for hour edits — this is a live, low-friction data entry surface.
- The "Add service line" dropdown only lists service lines meeting **all** of:
  - the parent project's `status` is `"active"`
  - the parent project's `is_active` is `true`
  - the current user is assigned to that `service_line` (i.e. is one of its consultants)
  - the `service_line`'s `is_active` is `true`

## Validation

**Placeholder — not yet specified.** This is a separate screen from §My Timesheet (Clocking)
above, not an extra mode bolted onto it. It's now the *only* place lock state ever changes — there
is no Submit step anywhere else (see §My Timesheet (Clocking)'s intro).

- **Access**: the literal `project_manager` role only — not inferred from `administrator` or
  `project_admin` — reached via the `timesheet` nav icon's dropdown, "Validation" item. Further
  scoped to the specific projects that user is assigned to as project manager — see
  [project.md § Project Managers](project.md#project-managers) for that assignment mechanism. See
  [home.md § Timesheet Menu](home.md#timesheet-menu) and
  [user.md § Role → Screen Access](user.md#role--screen-access).
- **Purpose**, from the top-level user stories: a `project_manager` can see their own timesheet,
  but also those of consultants **on projects they're assigned to**, and **lock**/**unlock**
  cells to freeze/unfreeze them from further edits.
- **Not yet defined** — see §Open Questions below for the full list of unresolved sub-questions,
  including several genuinely new ones this simplification introduces (lock granularity,
  gap-locking, self-lock, and whether locking carries any approval/audit meaning at all).

## Data Model

`time_entries` is the core underlying table both screens above are built on — table name plural,
matching every other table in this project (see
[database.md § Schema Conventions](../architecture/database.md#schema-conventions)) — §My
Timesheet (Clocking) writes unlocked rows to it; §Validation (once specified) is the only thing
that ever sets `is_locked = true` (or reverts it). An item in `time_entries` contains the
following information:

 - `id` UUID PK -- matches every other table's PK type in this project (see
   [database.md](../architecture/database.md))
 - `user_id` FK → Users, `ON DELETE CASCADE` -- a time entry's primary subject is the person who
   logged it; deleting that user should delete their entries, matching the FK behavior every
   other child-table relationship in this project uses (see
   [database.md](../architecture/database.md#tables))
 - `service_line_id` FK → service_lines, `ON DELETE CASCADE` -- same reasoning: a time entry
   can't outlive the service line it was logged against
 - `date` date (no time of day) -- The data on which the time was logged
 - `time_entry` `INTERVAL`, `NOT NULL`, `CHECK (time_entry >= interval '0' AND time_entry <=
   interval '24:00:00')` -- The actual duration logged (e.g. `01:00:00` for 1H). An earlier
   version of this doc specified `TIME` instead, reasoning that `TIME`'s natural ceiling at
   `24:00:00` would enforce the 24h domain constraint for free at the type level. That's true at
   the SQL level, but empirically false through this project's actual driver: `asyncpg` binds and
   decodes `TIME` exclusively via Python's `datetime.time`, whose `hour` field is capped at 23 —
   `24:00:00` is a value Postgres itself accepts but the driver can neither write nor read back
   (confirmed directly against a live connection). Since that ceiling can't actually be relied on
   in practice, the `CHECK` constraint above does the same job explicitly instead, and `INTERVAL`
   — which round-trips through `asyncpg`/Python's `datetime.timedelta` with no such landmine —
   replaces `TIME`. Named `time_entry`, not the bare `time` or `interval`, for naming-collision
   reasons that no longer strictly apply now that the type isn't `TIME`, but the name is kept
   as-is rather than re-litigated over a since-superseded rationale. The 0.5-increment rule (see
   §Interactions & Input Rules) is enforced at the API level, not a DB `CHECK` constraint —
   deliberate, matching how other app-level-only validation already works elsewhere in this
   project.
 - `comment` TEXT default NULL -- An optional comment. Unused in the current UI — deliberate
   scope-fencing for a later iteration, not an oversight
 - `last_updated_by` FK → Users, `ON DELETE SET NULL` -- **deliberately not `CASCADE`**, unlike
   `user_id`/`service_line_id` above: this column just records who last touched the row (e.g. a
   `project_manager`'s lock/unlock action), not whose data it is. Deleting that `project_manager`
   should never delete someone else's time entry as a side effect — the two FKs to `Users` on
   this table have
   different, not-interchangeable delete semantics. `last_updated_by`/`updated_at` update on
   *any* change to the row, including a lock/unlock that only touches `is_locked` and not
   `time_entry` — standard practice, not scoped to value-only edits
 - `created_at` timestampz default now()
 - `updated_at` timestampz default now()
 - `is_locked` boolean, default false
(user_id, service_line_id, date) -> unique constraint

Implication 1: It is not possible to log two different times against the same project service line for the same user.
This is intended. The design of the model is to remain simple (e.g. on the 8th of August, I spent 3H on project service line X) rather than finely grained (on the 8th of August, I spent 1.5H on project service line X, had a break of 2H then spent another 1.5H on project service line X)

### Indexes

- `(user_id, service_line_id, date)` — already backed by the unique constraint above (Postgres
  creates a supporting index for any `UNIQUE` constraint automatically); listed here so it's
  visible alongside the other index rather than only implied.
- `(user_id, date)` — supports the actual query §My Timesheet (Clocking) and (eventually)
  §Validation both run constantly: "this user's entries across a date range," without needing to
  know `service_line_id` up front (e.g. loading a whole period's grid in one query).

## Open Questions

The points below came out of a first review of this draft. Grouped roughly by severity;
addressing the "Critical" ones is a prerequisite for implementation, the rest can probably be
resolved alongside them or deferred. (Was titled "Review pass" — renamed to match every other
requirements doc's `## Open Questions` convention; several other docs already linked to
`timesheet.md#open-questions`, which didn't actually resolve to this section under its old
heading/slug until now.)

**Critical — blocks implementation as written**

- **The Validation screen — now the *entire* lock/unlock mechanism — is completely unspecified.**
  With Submit gone, this single placeholder screen carries everything that used to be split
  across My Timesheet's Submit button and the old Validate/re-open actions. Open sub-questions:
  - **Lock granularity** — per cell, per day, per service line's whole period, or bulk across an
    entire consultant + period in one action? (This is the direct replacement for the old Submit
    granularity question, now entirely on the `project_manager`'s side.)
  - **Gap-locking** (new, direct consequence of reinstating delete-on-zero — see §Persistence):
    if a `project_manager` locks a range that includes untouched (rowless) days, are those days
    materialized as locked `0` rows, or does locking silently skip gaps — leaving them open
    indefinitely, so a consultant could still add hours to a "hole" inside an otherwise-locked
    period? This needs an explicit answer; it didn't exist as a question under the old
    force-fill-everything Submit mechanism.
  - **Self-lock — resolved**: yes, no restriction. A `project_manager` who is also a `consultant`
    on the same project (an already-supported multi-role combination) can lock/unlock their own
    timesheet cells same as anyone else's — deliberately kept simple rather than adding a
    self-assigned-work carve-out. See [user.md § Open Questions](user.md#open-questions).
  - **Scope — resolved and implemented**: a `project_manager` can only lock/unlock timesheets for
    consultants assigned to service lines on projects where *they themselves* are assigned as
    project manager (see [user.md § Role → Screen Access](user.md#role--screen-access)) — this
    replaces the earlier version of this question (whether any `manager` could act system-wide,
    back when `project.md` had no concept of per-project responsibility). The assignment relation
    itself is implemented: see [project.md § Project Managers](project.md#project-managers) (the
    `project_managers` table and the Project Form's picker). **Still open**: how the Validation
    screen itself queries against that assignment and surfaces it in its UI — left for this doc
    to specify when the Validation screen is designed.
  - **Does "locked" carry any approval/audit meaning, or is it purely a mechanical edit-freeze?**
    (new) The old `validated` state implied a manager had reviewed and signed off — a real
    business capability for billing/payroll/audit purposes. The new model is deliberately weaker
    ("frozen from edits") and doesn't by itself say whether that reviewed-and-approved meaning
    still exists somewhere, or whether it's been dropped along with the complexity. Worth
    deciding explicitly rather than losing it silently.
  - How a `project_manager` finds/picks which consultant's timesheet to look at (presumably
    scoped to the consultants on their assigned projects, not every consultant in the system —
    another consequence of the scoping above worth confirming explicitly), and what read-only vs.
    editable states look like for whatever's shown, remain undefined too (carried over from the
    original placeholder).

**Resolved — raised by the "Removing a service line" revision above, since resolved**

- **Backend lock enforcement, bulk-clear mechanism, and the confirm/Confirm race** are all now
  resolved together by making `PUT /time-entries` a bulk, per-item-validated endpoint — see
  §Persistence's "API contract" above for the full design (array in, array out, `is_locked`
  checked per item server-side regardless of caller, `207 Multi-Status` on partial rejection, and
  the frontend's defined handling of that response for the clear-on-remove flow specifically).
  What's still open, not resolved by this: a concrete request-size sanity limit (see that section)
  — a minor implementation detail, not a design question.

**Edge cases / smaller inconsistencies**

- **Confirmation dialog button labels — resolved.** Uses this app's established
  Cancel/destructive-verb `AlertDialog` convention (matching every other confirm dialog in the
  app — see [frontend.md § Destructive Actions](../architecture/frontend.md#destructive-actions)),
  not literal "Yes"/"No" buttons — see §Interactions & Input Rules' "Removing a service line"
  above.
- **No cap/overflow behavior for many assigned service lines — resolved, intentional.** A
  consultant with many service lines across projects gets a longer mobile vertical list / a
  taller desktop sticky first column, scrolling naturally like any other long list in the app —
  no cap, no pagination, no collapsing. Not an oversight; there's no reason to special-case this.
