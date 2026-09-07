THIS IS A DRAFT - NOT YET REVIEWED AND NOT YET IMPLEMENTED

# Timesheet — User Stories

Two distinct screens live under this doc, both reached via the `timesheet` nav icon — see
[home.md § Timesheet Menu](home.md#timesheet-menu) for how the icon's behavior branches by role.
They're kept clearly separate below: one is the data-entry mechanism, the other is the
`project_manager`-only review workflow built on top of it.

- **My Timesheet** (see §My Timesheet (Clocking) below) — where a user logs their own time
  against a `Service Line` they're assigned to (see [project.md](project.md)). Cells are freely
  editable — **there is no Submit step** — until a `project_manager` locks them via §Validation.
- **Validation** (see §Validation below) — where a `project_manager` sees consultants' submitted
  timesheets **on projects they're assigned to as project manager** (see
  [user.md § Entity](user.md#entity) for the `project_admin`/`project_manager` split — this was
  gated by a single `manager` role before that split), can edit them the same way a consultant
  edits their own, and **locks**/**unlocks** a whole service line's period at a time to
  freeze/unfreeze it from further edits.

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
  one place this simplicity has a real cost is in §Validation: locking a date range that includes
  untouched (rowless) days has to materialize those gaps as locked `0` rows — see
  [§Validation § Lock / Unlock](#lock--unlock) — so this "no reason to exist as a row" rule is
  specifically about an *unlocked* `0`, not `0` rows in general.
- On blur, if the value is `> 0`: the row is upserted (`INSERT ... ON CONFLICT (user_id,
  service_line_id, date) DO UPDATE`, matching the table's unique constraint) with `is_locked =
  false`. A row created this way is always unlocked by construction — the consultant's own save
  path can never set `is_locked = true`; only a `project_manager`'s action on §Validation can.
- This flow only ever applies while `is_locked = false` — once a row is locked its cell renders
  read-only (see the user stories above), so there's no blur-to-save path to guard against
  separately.
- **Saving a new entry against a service line the user is no longer assigned to must error, not
  silently succeed** — and, **resolved**, the UI doesn't wait for that error to happen: every cell
  on a service line the entry's owner is no longer currently assigned to is **read-only**,
  regardless of `is_locked`. Historical data still displays in full (see §State's population rule
  and §Interactions & Input Rules' removal rule — unassignment never hides a line with real
  history), it just can't be edited or added to anymore once the person it belongs to isn't
  assigned to it — the UI proactively reflects that rather than letting someone type into a cell
  that would only fail on blur. This is a *third*, distinct reason a cell can be read-only,
  alongside `is_locked` — see §Both views above for how the two are told apart visually, and
  §Validation § Scope above for why this applies identically there (a `project_manager`'s
  override is subject to the exact same rule, checked against the *consultant's* current
  assignment, not the `project_manager`'s own).

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

Both views have clean UI feedback on the cell's editability — **three** states (revised from an
earlier two-state design — see §Persistence above for the rule that added the third):
 - **Open** (`is_locked = false`, and the entry's owner is currently assigned to the service
   line): standard, editable.
 - **Locked** (`is_locked = true`, regardless of current assignment): read-only, with a **light
   red background** — deliberately more specific than "greyed out" (an earlier draft's wording):
   a locked cell needs to read as "frozen, someone else's action," not just disabled, and the
   same rendering is shared verbatim between My Timesheet and Validation (see §Validation below)
   — a consultant sees the exact same light-red cell on their own timesheet that a
   `project_manager` sees on Validation, since both screens render cells through the same
   component.
 - **Unassigned** (`is_locked = false`, but the entry's owner is *not* currently assigned to the
   service line — historical data from a since-removed assignment): read-only, **greyed out**
   (reusing the plain "disabled" treatment the two-state design used for Locked, now free to mean
   something more specific now that Locked has its own distinct light-red styling) — with a
   native `title` tooltip explaining why (same lightweight pattern
   `RemoveServiceLineControl`'s disabled state already uses, rather than introducing a
   `TooltipProvider` for this too). **Locked wins if both are true** — a locked row on a
   since-unassigned line renders as Locked (light red), not Unassigned (grey); Unassigned only
   ever applies to a genuinely unlocked row. Applies identically on Validation, checked against
   the *consultant's* current assignment, not the viewing `project_manager`'s own (see
   §Validation § Scope above).

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

This is a separate screen from §My Timesheet (Clocking) above, not an extra mode bolted onto it.
It's the *only* place lock state ever changes — there is no Submit step anywhere else (see §My
Timesheet (Clocking)'s intro). A `project_manager` does not have "their own" separate timesheet
here — their own time is still logged on §My Timesheet (Clocking), like anyone else's; this
screen is exclusively for reviewing/editing/locking *consultants'* timesheets.

- **Access**: the literal `project_manager` role only — not inferred from `administrator` or
  `project_admin` — reached via the `timesheet` nav icon's dropdown, "Validation" item. Further
  scoped to the specific projects that user is assigned to as project manager — see
  [project.md § Project Managers](project.md#project-managers) for that assignment mechanism. See
  [home.md § Timesheet Menu](home.md#timesheet-menu) and
  [user.md § Role → Screen Access](user.md#role--screen-access).
- **Purpose**, from the top-level user stories: a `project_manager` can see consultants'
  timesheets **on projects they're assigned to**, edit them the same way the consultant would
  edit their own, and **lock**/**unlock** a whole service line's period at a time to
  freeze/unfreeze it from further edits.

### Implementation note: one shared mechanism, not two

**This is an architectural requirement, not just a preference.** My Timesheet (Clocking) and
Validation are two views over the *same* mechanism — a grid/day-strip of service-line rows for a
selected Week/Month period, autosaving cells on blur — not two independently-built screens that
happen to look similar. Validation must reuse the same components My Timesheet (Clocking) already
uses for: the Shared Header (`periodType`/`periodDate` switching, prev/next, period label — see
§Shared header above), the responsive Mobile/Desktop split (§Mobile view/§Desktop / tablet view
above), the per-cell input/autosave behavior (§Persistence above, including its bulk `PUT
/time-entries` contract), and the "Add service line"/"Removing a service line" mechanics
(§Interactions & Input Rules above). Validation's own additions — stacking multiple consultants'
timesheets, and the lock/unlock control — must be expressed as parameters/composition over that
shared mechanism (e.g. "whose timesheet," "how many, stacked," "does this row get a lock
control") rather than a parallel implementation. Concretely, nothing described below should
require its own copy of the grid, the cell-rendering logic, or the period-switching logic; the
lock/unlock control is the one genuinely new piece of UI, added *alongside* the existing
remove-service-line control, not replacing any of it. This matters enough to call out explicitly
because getting it wrong here is exactly how a codebase ends up with two subtly-diverging
implementations of "a timesheet grid" to maintain forever after.

### Screen layout

- **One shared header for the whole screen** (§Shared header above, reused verbatim) — a single
  `periodType`/`periodDate` selection governs every consultant's timesheet shown below at once.
  There is no per-consultant period picker; reviewing "everyone's August" is the point.
- **One block per consultant**, each consisting of:
  - A header showing the consultant's name, in bold (their `full_name` — see
    [user.md](user.md)). Nothing else in the header; project/service-line detail is still shown
    per-row exactly as on My Timesheet (project name + service line name — see §Desktop / tablet
    view above).
  - That consultant's timesheet, rendered through the exact same responsive component described
    in §Screen layout's implementation note above (day-strip on mobile, spreadsheet grid on
    desktop/tablet), scoped per §Scope below.
- **A shadcn/ui `Separator` between consecutive consultant blocks** — after a block, before the
  next one; no separator before the first block or after the last.
- **Consultant block order**: proposed ascending by `full_name`, matching this doc's existing
  row-ordering convention elsewhere (§State above) — not explicitly requested; flag if a
  different order (e.g. by project) is wanted instead.

### Scope: what a `project_manager` sees and can touch

- **Project-scoped, not consultant-scoped.** A consultant can be assigned to service lines on
  projects the viewing `project_manager` is *not* assigned to as project manager (see
  [project.md § Project Managers](project.md#project-managers)) — those service lines are simply
  never shown here, on this consultant's block or anywhere else on this screen. This is a hard
  filter applied before anything else below, not a greyed-out/locked-looking placeholder for
  out-of-scope lines — they don't exist on this screen at all, the same way an entirely
  unrelated consultant's timesheet doesn't.
- **Which consultants show up at all — revised: static membership, not data-dependent.** Every
  consultant assigned to at least one service line meeting the same eligibility rule §Interactions
  & Input Rules' "Add service line" already uses (project `status = "active"`, project
  `is_active = true`, service line `is_active = true`, consultant assigned) on a project the
  `project_manager` is assigned to (see [project.md § Project Managers](project.md#project-managers))
  gets a block — **unconditionally, whether or not they have any logged time for the
  currently-displayed period.** This replaces the earlier has-data-or-added-this-period rule at
  the consultant level (that rule now applies one level down — see the next bullet). A consultant
  who's ever logged time on an in-scope-at-the-time service line also keeps their block via that
  historical data even if since unassigned or the project's gone inactive — the same "historical
  data stays visible regardless of current assignment" principle §State already establishes for
  My Timesheet, just applied one level up. **This is what resolves the earlier "zero-data
  consultant discovery" gap**: a newly-assigned consultant with nothing logged yet still gets a
  block, empty, ready to add a line into — see [Open Questions](#open-questions) below, now
  marked resolved.
- **Which service lines actually show, *within* a consultant's block — unchanged.** The existing
  rule (§State above): a line shows if it has any entry for the currently-displayed period, or
  was added via "Add service line" while viewing this period — intersected with the project-scope
  filter above. A consultant who qualifies for a block per the bullet above but has no data this
  period, and hasn't had a line added yet, gets a block with **zero rows** — rendered through the
  exact same empty state My Timesheet's own component already has ("No service lines added yet.
  Use 'Add service line' below to start logging time." — see §Mobile view/§Desktop / tablet view
  above), inherited for free rather than needing its own design, per the implementation note
  above.
- **"Add service line," on a given consultant's block**: same UI as My Timesheet's own (a
  constrained dropdown, not free text — see §Interactions & Input Rules above), and the same
  eligibility filters (active project, active service line) — but computed from the
  `project_manager`'s perspective, not the consultant's: service lines where **(a)** the
  `project_manager` is assigned to the parent project and **(b)** this specific consultant is
  assigned to the service line (i.e. one of its consultants — same `service_line_consultants`
  check My Timesheet's own eligibility rule uses, just from the other side). Both conditions, not
  either. This is the exact same set that determines block membership above, which is why an
  empty block's "Add service line" dropdown is never actually empty — it always has at least the
  service line(s) that qualified this consultant for a block in the first place (plus any others
  they're also assigned to under this `project_manager`'s scope).
- **Editing ("override")**: a `project_manager` can edit any *unlocked* cell on any displayed
  consultant's block, through the exact same input/autosave-on-blur mechanism a consultant uses
  on their own timesheet (§Persistence above, same bulk `PUT /time-entries` contract) — there is
  no separate "override" endpoint or mode. `last_updated_by` on the resulting row is the
  `project_manager`, not the consultant (§Data Model above already accounts for this — it's why
  that column exists at all). **Editing a locked cell is not possible directly** — `PUT
  /time-entries` already rejects a write against `is_locked = true` unconditionally, regardless
  of caller (§Persistence's API contract above: "this endpoint never grants that authority to
  anyone, including the original consultant") — a `project_manager` who needs to change a locked
  value must unlock the service line's period first (see §Lock / Unlock below), make the edit,
  and optionally re-lock afterward. This is deliberate, not a gap: it means the write endpoint
  never has to special-case "unless the caller is a project_manager," keeping locked genuinely
  meaning locked, for everyone, through that one endpoint.
- **Removing a service line, on a consultant's block — resolved: full three-branch behavior,
  unchanged.** Branch 2 (confirm, then bulk-clear the period's logged time — see §Interactions &
  Input Rules above) applies exactly as on My Timesheet, including when a `project_manager`
  invokes it against a consultant's own logged time — this is a direct consequence of "a
  `project_manager` can override inputs" extending to removal, not just editing individual cells.
  Branch 3 (any locked entry blocks removal entirely) still applies unchanged, same as always.

### Lock / Unlock

- **Granularity: one whole service line's period, per consultant — not per cell, not per day.**
  This resolves the earlier open question of lock granularity. A single lock/unlock action always
  targets exactly the row currently in view (one consultant, one service line) across every day
  in the *currently-displayed* period (`days` — Week or Month, whichever is selected — see §State
  above) — the same period-scoping already established for "Removing a service line" above.
- **Control**: a new icon-button on the row, positioned immediately to the **left** of the
  existing remove ("×") control (§Interactions & Input Rules above) — so the row's action order
  becomes lock/unlock, then remove. Only rendered on Validation (via the shared component's
  "does this row get a lock control" parameter — see the implementation note above); My Timesheet
  (Clocking) never shows it, since a consultant has no locking authority over their own row.
- **Icons represent the action a click performs, not the row's current state**: `lucide-lock`
  (closed) means "click to lock"; `lucide-lock-open` (open) means "click to unlock." Concretely:
  - **Shows `lucide-lock`** (→ clicking **locks**) whenever *any* day in the currently-displayed
    period is not locked for this service line/consultant — whether that day has an unlocked
    entry, or no entry at all (a gap). **Rule, stated directly**: if at least one day in the
    period isn't locked, the icon shows lock.
  - **Shows `lucide-lock-open`** (→ clicking **unlocks**) only when *every* day in the
    currently-displayed period is already locked for this service line/consultant.
  - **Worked example from the request**: a `project_manager` locks Week 34 (all 7 days become
    locked). They switch to Month view. The rest of the month is untouched, so the icon still
    shows `lucide-lock` — clicking it now locks every remaining unlocked/gap day in the *whole
    month*, Week 34's already-locked days included in the target period but left as-is (locking
    an already-locked day is a no-op, not an error). A lock action only ever moves days *toward*
    locked; it never revisits or unlocks anything.
- **What "lock" actually does, per day in the target period** (this resolves the earlier
  gap-locking open question): for a day with an existing unlocked row, set `is_locked = true`,
  value unchanged. For a day with **no** row at all (a gap), create one with `hours = 0` and
  `is_locked = true` — i.e. locking *does* materialize gaps, deliberately, because "lock the
  entire service line for the period" (as specified) only means something uniform if every day
  in that period ends up in the same state. This is a narrow, explicit exception to §Persistence's
  "a `0` entry has no reason to exist as a row" rule — that rule is about an *unlocked* `0`
  specifically, not `0` rows in general (see §Persistence above, updated to say so).
  **Resolved — must be written as a single atomic upsert per day, never a read-then-decide.**
  `INSERT ... ON CONFLICT (user_id, service_line_id, date) DO UPDATE SET is_locked = true` — the
  conflict branch touches `is_locked` **only**, never `hours`; the insert branch's `hours = 0`
  applies solely when no row exists at the instant the statement runs. This is what closes the
  race against a concurrent consultant edit (see §Open Questions below): whichever write actually
  reaches Postgres first, the other composes correctly on top of it — a consultant's value that
  lands moments before a lock request is locked *as entered*, never silently zeroed out by it.
  Not a read-then-write check at the application layer; Postgres's own row-level serialization on
  the unique key is what makes this safe under concurrency, not application code guessing who won.
- **What "unlock" actually does, per day in the target period**: for a day whose row has
  `hours > 0`, set `is_locked = false` (value unchanged, now editable again). For a day whose row
  has `hours == 0` (i.e. one of lock's own gap-fill rows, since a genuine consultant-entered `0`
  can never exist per §Persistence), **delete the row** rather than leaving a `0`, unlocked —
  restoring the true gap that existed before it was locked, and keeping the existing invariant
  intact ("a row exists only if `hours > 0` or `is_locked = true`," now stated as the general
  rule rather than assumed).
- **"Locked" carries no approval/audit meaning — resolved.** It is purely a mechanical
  edit-freeze, not a "reviewed and signed off" signal the way the old `validated` state implied.
  The one thing that *is* recorded is *who* locked (or unlocked) a row and *when* —
  `last_updated_by`/`updated_at` (§Data Model above) already capture this as a side effect of
  being a normal row update, the same as any other change to the row. That's a plain audit trail
  of the mechanical action, not an approval/sign-off status — there's no separate "reviewed by"
  concept, and nothing currently reads `last_updated_by` as meaning anything beyond "this is who
  last touched this row."
- **No race-outcome reporting to the `project_manager` — resolved, by design.** Once the atomic
  write above guarantees a lock action always ends up locking whatever value genuinely existed
  the instant it ran, there's no *wrong* outcome left to report — only "the right value got
  locked, possibly a beat later than you assumed." The consultant's own side already surfaces the
  race when it goes the other way (their `PUT /time-entries` item comes back rejected per
  §Persistence's existing contract — toast, revert, no new mechanism needed). Deliberately not
  building richer diff/report-back for the `project_manager` on top of that — see §Open Questions
  below for why that was considered and set aside rather than just not thought of.
- **Visual feedback**: a locked cell renders with a **light red background** (see §Both views
  above, updated) — the same rendering on both My Timesheet (Clocking) and Validation, since both
  render cells through the same component (see the implementation note above).
- **No confirmation dialog on lock or unlock — resolved, by design.** Matches this app's "live,
  low-friction editing surface" philosophy already established for hour edits (§Interactions &
  Input Rules above) rather than
  [frontend.md § Destructive Actions](../architecture/frontend.md#destructive-actions)'s
  confirm-before-destructive-action rule — consistent with neither action destroying data (lock
  preserves values; unlock's only deletion is of a `0` gap-fill row that was never real data to
  begin with).

#### API contract: locking is not part of `PUT /time-entries`

§Persistence's API contract above already establishes that `PUT /time-entries` never grants
unlock authority to anyone, including a `project_manager` — locking/unlocking needs its own
mechanism entirely. Proposed shape, mirroring that same contract's rigor:

- A new endpoint — e.g. `PUT /time-entries/lock` — taking the target consultant (`user_id`), the
  `service_line_id`, the date range (`start_date`/`end_date` — i.e. whatever `days` currently is
  on the caller's screen), and the target `locked` boolean (`true` to lock, `false` to unlock).
  One call per lock/unlock click — this is a single (consultant, service line, period) action,
  not a bulk array the way `PUT /time-entries` is (there's no equivalent "many independent items"
  shape here — see [Open Questions](#open-questions) below for the one place this could still
  raise a partial-failure question).
- **Authorization, all required**: caller holds `project_manager`; caller is assigned (via
  `project_managers`) to the project that owns `service_line_id`; the target consultant
  (`user_id`) is actually assigned to `service_line_id` (i.e. is one of its consultants). Any
  failing check is a rejection, not a partial success.
- **Response**: proposed as the resulting set of `TimeEntryOut` rows for that
  (`user_id`, `service_line_id`) across the requested date range, post-lock/unlock — same
  "return authoritative state, don't make the client guess" pattern §Persistence's bulk contract
  already uses — so the frontend can resync `entries` for that row directly from the response,
  the same way it already does for `PUT /time-entries`.

#### API contract: `GET /time-entries/managed` — one call loads the whole screen

`GET /time-entries` (§My Timesheet (Clocking)'s own read endpoint) is deliberately scoped to "the
calling user's own entries" — it has no notion of another user or a project-scoped consultant
list, and reshaping it to sometimes mean "my team's entries, grouped" was considered and
rejected: it would make the endpoint's response shape and authorization depend on which query
params were passed, breaking the "one endpoint, one predictable meaning" rule this app's other
endpoints already follow (`GET /time-entries/eligible-service-lines` included). A caller-supplied
"whose data" parameter was also considered and rejected for the same reason every other endpoint
in this app derives identity from the auth cookie rather than a client-supplied id: there's no
legitimate value it could hold other than the caller's own, making it redundant at best and an
easy thing to get wrong at worst.

Instead: a new, purpose-built endpoint, `GET /time-entries/managed?start_date=&end_date=` —
naming to match this doc's own recommendation, distinct from a rejected `/time-entries/team`
alternative.

- **No identity parameter.** Like `GET /time-entries/eligible-service-lines`, the caller's
  identity and role come entirely from the auth cookie (`get_current_user`). The endpoint
  requires the literal `project_manager` role (`require_roles("project_manager")`, same pattern
  every other role-gated endpoint in this app already uses) — a 403 otherwise, not a
  differently-shaped response.
- **One query, all server-side scoping**: joins `project_managers` (this caller's assigned
  projects) → eligible `service_lines` (the same active-project/active-service-line filters
  §Interactions & Input Rules' "Add service line" already uses) → `service_line_consultants` for
  the roster, unioned with anyone holding historical data on an in-scope-at-the-time line (see
  §Scope above) — then one `time_entries` query across all those service lines for the requested
  date range, grouped by consultant. This is the same "one indexed query beats N round trips"
  reasoning `PUT /time-entries`'s own bulk contract above is already built on, applied to reads.
- **Response, grouped by consultant** — one entry per in-scope consultant, each carrying:
  - `user_id`, `full_name` (renders the bold consultant-name header — see §Screen layout above)
  - `entries`: that consultant's `time_entries` for the requested range, restricted to service
    lines under *this* `project_manager`'s scope only (never the consultant's service lines on
    projects this `project_manager` isn't assigned to — §Scope's hard project-scoping rule) —
    same `TimeEntryOut` shape §Data Model already defines, unchanged.
  - `eligible_service_lines`: **(b) embedded directly in this same response**, rather than a
    separate parameterized call to `eligible-service-lines` — *every* service line this specific
    consultant is currently eligible for under this `project_manager`'s scope (§Scope above's
    both-conditions rule: `project_manager` assigned to the project **and** this consultant
    assigned to the service line), same unfiltered `EligibleServiceLineOut` shape `GET
    /time-entries/eligible-service-lines` already defines and — deliberately — the same
    *unfiltered* shape too: this is the raw eligibility set, not pre-filtered down to only
    addable ones. Two things are derived from it client-side, mirroring exactly how My
    Timesheet's own `eligibleLines`/`addOptions` split already works (§State above): the "Add
    service line" dropdown's options (this set, minus whatever's already shown on the block —
    the existing `addOptions` filter, unchanged), **and** — new, needed for §Persistence's
    "Unassigned" cell state above — whether an *already-shown* row is still editable at all: a
    row's service line not being in this consultant's `eligible_service_lines` is exactly what
    "no longer currently assigned" means, checked against the consultant, not the caller. Chosen
    over a second round trip per consultant because this screen's whole usage pattern is "load
    once, review everyone" — a bigger single response beats N follow-up calls here, the same
    reasoning that ruled out Option B's per-consultant loop above.
  A consultant with nothing logged this period and nothing added yet still appears, with
  `entries: []` — this is what makes §Scope's "static membership, unconditional" rule real: the
  roster comes from this same call, not a separate one.
- `GET /time-entries` and `GET /time-entries/eligible-service-lines` are **unchanged** — Validation
  never calls either; My Timesheet (Clocking) keeps using them exactly as today.
- No pagination on the consultant list — consistent with this doc's existing "no cap, scrolls
  naturally" position (§Open Questions below), extended here the same way it already covers many
  service lines or many empty consultant blocks.

## Data Model

`time_entries` is the core underlying table both screens above are built on — table name plural,
matching every other table in this project (see
[database.md § Schema Conventions](../architecture/database.md#schema-conventions)) — §My
Timesheet (Clocking) writes unlocked rows to it; §Validation is the only thing that ever sets
`is_locked = true` (or reverts it), including materializing/removing the `0`-hour gap rows its
own lock/unlock actions need (see §Validation § Lock / Unlock above). An item in `time_entries`
contains the following information:

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

- **Resolved — zero-data consultant discovery.** §Validation § Scope above now defines "which
  consultants show up at all" as static membership (assigned to an eligible in-scope service
  line, or has historical data on one) rather than data-dependent — a consultant block always
  exists once someone qualifies, whether or not they've logged anything for the currently-viewed
  period, so there's no longer a chicken-and-egg problem creating the first block. The read
  endpoint this needs is now fully specified too — see §Validation's `GET /time-entries/managed`
  API contract above.
- **Resolved — lock/unlock race against a concurrent consultant edit.** Split into the two things
  this was actually conflating: whether the race can *corrupt data*, and whether it needs
  *reporting*.
  - **Corruption — closed, not a judgment call.** §Validation § Lock / Unlock above now requires
    the per-day lock write to be a single atomic `INSERT ... ON CONFLICT DO UPDATE SET is_locked
    = true` (never touching `hours` in the conflict branch) rather than a read-then-decide at the
    application layer. Postgres's own row-level serialization on the unique key means whichever
    write — the consultant's save or the `project_manager`'s lock — actually lands first, the
    other composes correctly on top of it. A consultant's value can no longer be silently zeroed
    out by a lock landing moments later.
  - **Reporting — resolved, deliberately minimal.** Once corruption is off the table, there's no
    wrong outcome left to narrate to the `project_manager` — only "the right value got locked,
    maybe a beat later than assumed." The consultant already learns of the race when it goes the
    other way, via the existing rejected-item path in §Persistence's `PUT /time-entries` contract
    (no new mechanism). A richer diff/report-back for `PUT /time-entries/lock` itself (an
    expected-prior-state input, a `207`-style per-day response) was considered — architecturally
    consistent with the bulk endpoint's own pattern, so not a foreign idea — but rejected as
    disproportionate engineering for a millisecond-window race whose only remaining outcome,
    once atomic, is already correct.
- **Resolved — "locked" carries no approval/audit meaning.** Purely a mechanical edit-freeze; the
  old `validated` state's implied "reviewed and signed off" meaning is not carried forward.
  `last_updated_by`/`updated_at` (§Data Model above) do record who locked/unlocked a row and
  when, as a side effect of it being a normal row update like any other — a mechanical audit
  trail, not an approval/sign-off status. See §Validation § Lock / Unlock above.
- **Resolved — "Removing a service line" applies in full on a consultant's block, including
  branch 2.** A `project_manager`'s ability to override a consultant's input extends to removal,
  not just editing individual cells — branch 2 (confirm, then bulk-clear) works exactly the same
  whether it's your own timesheet or a consultant's. Branch 3 (any locked entry blocks removal
  entirely) is unaffected. See §Validation § Scope above.
- **Resolved — no confirmation dialog on lock/unlock, by design.** See §Validation § Lock / Unlock
  above.
- **Lock granularity, gap-locking, self-lock, and scope are all resolved** — see §Validation §
  Lock / Unlock above for granularity (one whole service line's period, per consultant) and
  gap-locking (locking materializes gap days as locked `0` rows; unlocking removes any that
  weren't real data), [user.md § Open Questions](user.md#open-questions) for self-lock, and
  [project.md § Project Managers](project.md#project-managers) for the scope mechanism itself,
  now fully specified in how the screen surfaces it (§Validation § Scope above). Carried here
  only as a pointer, not restated.

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
  **Extends to Validation's consultant blocks too**, now that block membership is unconditional
  (§Validation § Scope above) rather than data-gated: a `project_manager` on a project with many
  consultants sees many blocks, most potentially empty for any given period — the same "scrolls
  naturally, no cap" answer applies, consistent with everything else in this doc that could
  otherwise grow long. Not re-opening this as a fresh question just because the specific case
  (many *empty* blocks, not many *populated* rows) is new.
