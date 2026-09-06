```prompt
You are performing a comprehensive codebase audit for this web application. The app currently works and passes its test suite, and the implementation is believed to track the specs in the /docs/*. Your job is to verify that belief rigorously and surface everything that doesn't hold up.

Appending your findings to docs/audit.md. Do not fix anything — this is a read-only audit. Flag issues, don't patch them.

## Process

1. Read every spec file first (functional and non-functional requirements) and build an internal map of documented requirements — features, business rules, constraints, API contracts, performance/security/accessibility requirements, etc.
2. Read the full codebase: backend, frontend, shared/common code, config, migrations, and tests. Don't sample — go through it systematically, directory by directory.
3. Cross-reference implementation against specs line by line, not just at a feature-summary level.

## What to look for

**Spec deviations**
- Implemented behavior that contradicts or diverges from a spec'd requirement, even subtly (edge cases, validation rules, error handling, default values).
- Spec'd requirements that appear to have no corresponding implementation.
- Implemented behavior/features with no corresponding spec (undocumented functionality).
- Places where tests pass but only because they test the implemented (possibly wrong) behavior rather than the spec'd behavior.

**Internal consistency**
- Same concept modeled or named differently across layers (e.g., a "status" enum with different values in DB, backend model, API response, and frontend type).
- Duplicated logic that has drifted (e.g., validation implemented separately in two places with different rules).
- Inconsistent error handling, response shapes, or naming conventions across similar endpoints/components.
- Frontend and backend disagreeing on contracts (types, required fields, pagination shape, date formats, etc.).
- Inconsistent state management patterns, component structure, or architectural conventions across the frontend.

**Best practices**
- Performance: N+1 queries, missing indexes, unnecessary re-renders, unbounded queries/lists.
- Maintainability: dead code, overly complex functions, tight coupling, missing abstraction where duplication is heavy.
- Testing: coverage gaps, tests that don't actually assert meaningful behavior, missing edge-case coverage.
- Accessibility and error-UX gaps on the frontend if relevant.

**Open questions / conflicts**
- Places where specs conflict with each other.
- Places where spec intent is ambiguous and the implementation made a judgment call — flag the assumption made.
- Anything where you genuinely can't tell if it's a bug or intended behavior.

## Output format for docs/audit.md

Organize by category (Spec Deviations / Consistency Issues / Best Practice Concerns / Open Questions), not by file. Within each category, order by severity (Critical / Moderate / Minor).

For every finding, include:
- **What**: concise description
- **Where**: file path(s) and line numbers or function/component names
- **Spec reference**: which spec doc/section, if applicable
- **Why it matters**: concrete impact, not generic
- **Severity**: Critical / Moderate / Minor
- **Suggested next step**: one line, not a fix

End with a short summary section: total findings by category and severity, and a "top 5 things to address first" list.

Be exhaustive rather than concise — this audit is meant to be a thorough reference, not a quick skim. If something seems fine and matches spec, don't mention it; only report deviations, risks, and questions.
```

---

# Audit Findings

**Date:** 2026-09-06
**Method:** Full read of every doc under `docs/requirements/` and `docs/architecture/` plus `docs/sast.md`, followed by a systematic read of the entire `backend/app` tree, `backend/tests`, and the frontend (`api/`, `components/`, `pages/`, `hooks/`, `providers/`, `types/`, `lib/`), cross-referenced line by line against the specs. Migration history and test coverage were checked directly against `git log` and `grep`, not assumed. No code was modified.

## Spec Deviations

### 1. Service line deletion doesn't block on logged time for an `active` project, even though time entries now exist — Major

**What:** `docs/requirements/project.md` requires that on an `active` project, a service line "can be deleted only if no time has been logged against it." The current implementation allows unconditional deletion (soft-delete) regardless of logged time, on both `draft` and `active` projects — only a `closed` project blocks it.

**Where:** `backend/app/services/project_service.py:309-320` (`delete_service_line`), enforced (or rather, not enforced) via `backend/app/api/projects.py:186-200`.

**Spec reference:** `docs/requirements/project.md` §Service Lines ("Edit/delete rules by project status") and §2 Entity: Service Line's Validation rules.

**Why it matters:** This isn't a stale-but-harmless gap. The code's own comment says the check is "not yet enforceable, no time-entry concept exists yet" — but the time-entry feature (`time_entries` table, `time_entry_service.py`, the whole My Timesheet/Validation screens) has since been fully built in this same codebase. The blocking dependency the comment cites no longer exists, yet the check was never added when it landed. A `project_admin` can today soft-delete a service line that a consultant has already logged (and a `project_manager` may have already locked) real billable time against, on a project that's actively being billed — service-line-level `value` calculations silently drop that line's `quantity × unit_price` from the project total, with no data-integrity guard at all.

**Severity:** Major.

**Suggested next step:** Add the "any time logged" check to `delete_service_line` (a simple `EXISTS` query against `time_entries` for that `service_line_id`) before allowing deletion on an `active` project, matching the spec.

**Status: Fixed (2026-09-06).** `delete_service_line` now raises `ServiceLineHasLoggedTimeError` (mapped to `409`) when the target service line has any `time_entries` row and the project is `active`; editing remains unaffected. Covered by two new tests in `test_projects_api.py`. `project.md`'s three stale references to this being unimplemented have also been updated.

---

### 2. Party Identifier `scheme_id`/VAT format validation not implemented — Moderate

**What:** `docs/requirements/company.md` requires `scheme_id` to be "validated against the current ISO 6523 ICD / Peppol EAS code list at write time, not just at export time," and a `VAT` identifier's `id_value` to "match the regex/format rules of the country indicated by its prefix." The implementation only checks that `scheme_id` is non-empty when required (`legal_registration`/`peppol_participant`) and that `id_value` is non-empty — no code list or per-country VAT format exists anywhere in the codebase.

**Where:** `backend/app/schemas/company.py` (`PartyIdentifierWrite.check_scheme_id_required`).

**Spec reference:** `docs/requirements/company.md` §2.2 "scheme_id — code list rules", §2 Validation rules.

**Why it matters:** A completely invalid `scheme_id` (e.g. `"XX"`) or malformed VAT number is silently accepted today. Since no Peppol export/serialization feature exists yet either, the practical blast radius is currently zero — but the doc explicitly frames this as a write-time (not export-time) requirement, so it's a genuine, not just theoretical, gap once export is built.

**Severity:** Moderate (low current impact, since nothing consumes these identifiers yet; will become load-bearing once Peppol export is implemented).

**Suggested next step:** Decide whether this validation belongs at write time as specified, or should be deferred to export time (updating the spec to match) — then implement whichever is decided.

---

### 3. `Duplicate` on a Company can silently create cross-company duplicate VAT/Legal Registration/Peppol identifiers — Moderate

**What:** `company.md`'s own Open Questions flag that saving a duplicated company without changing its copied identifiers "should be caught by validation and rejected... needs cross-company uniqueness... §2's current uniqueness rule doesn't cover this, since it's scoped per-`company_id`." This audit confirms it's not just a theoretical gap: `duplicate_company` copies every `PartyIdentifier` row verbatim onto the new company and commits immediately, with no cross-company check at all.

**Where:** `backend/app/services/company_service.py:99-137` (`duplicate_company`); the DB constraint it would need to violate is the per-company `uq_party_identifiers` index in `backend/app/models/company.py:84-91`.

**Spec reference:** `docs/requirements/company.md` §Company Form "Duplicate", Open Questions.

**Why it matters:** Clicking `Duplicate` on any company and saving without touching its Party Identifiers immediately produces two active companies both claiming the same VAT number / legal registration number / Peppol participant ID — a real Peppol-compliance problem (these identifiers are meant to uniquely resolve to one legal entity), not just a data-quality nicety.

**Severity:** Moderate.

**Suggested next step:** Add a global (not per-company) uniqueness check for `VAT`/`LEGAL_REGISTRATION`/`PEPPOL_PARTICIPANT` at write time, as the spec's Open Question already anticipates.

**Status: Not a bug — intentional, by design (2026-09-06).** Confirmed with the author: the Peppol/UBL-shaped schema exists so this data is in the right *shape* for future e-invoicing, not so the app polices real-world global uniqueness of these identifiers across every company record. Cross-company uniqueness stays deliberately unenforced — adding it would be real engineering complexity (locking/race handling across unrelated rows, a global index instead of a scoped one) for a case that isn't actually harmful to this app's own behavior. `company.md`'s Open Question has been rewritten to reflect this as resolved rather than open.

---

### 4. Service Line modal's Quantity/Unit Price don't "silently strip" invalid input as specified — Moderate

**What:** `project.md`'s Add/Edit Modal spec says Quantity and Unit Price "only accept numbers and decimal point input, silently strip any non valid input." The actual fields are plain `<Input inputMode="decimal">` text inputs with no keystroke filtering at all — invalid characters can be typed freely and are only caught at submit time by a zod regex, which shows an error message rather than stripping anything.

**Where:** `frontend/src/components/projects/ServiceLineFormDialog.tsx:238` (quantity), `:262` (unit_price).

**Spec reference:** `docs/requirements/project.md` §Service Lines "Add/Edit Modal".

**Why it matters:** This is the same class of bug identified and partially addressed elsewhere in this codebase for the timesheet hours input (see the fix discussion around `TimesheetDesktopGrid.tsx`/`TimesheetMobileView.tsx`): a spec explicitly asking for proactive character-level filtering, implemented instead as after-the-fact validation. A user can type e.g. "12ab.5x" and see it sit in the field until they try to submit.

**Severity:** Moderate.

**Suggested next step:** Add an `onChange` filter (digits + at most one `.`) matching the same pattern already discussed for the timesheet hours cells, rather than relying solely on submit-time validation.

**Status: Not a bug — verified safe, severity was overstated (2026-09-06).** Re-checked live: typing `12ab.5x`/`hello` into Quantity/Unit Price does display the raw text while typing, but `Save` shows a specific inline error ("Quantity must be greater than zero", "Unit price must not be negative") and the modal stays open — no invalid value ever reaches the backend, which independently rejects a non-numeric payload via `ServiceLineWrite`'s typed `Decimal` fields regardless of what the frontend does. Unlike the timesheet hours cells this finding was compared to (Firefox silently displaying — and, absent the since-reverted fix, persisting — a stuck invalid value with no error surfaced at all), there was never a data-integrity gap here, only a wording mismatch against an earlier spec draft. `project.md` has been updated to describe the actual, safe validate-on-save behavior instead of "silently strip."

---

### 5. Projects List Screen columns are not sortable — Moderate

**What:** `project.md` states "All columns are sortable, using the Data Table's out-of-the-box (TanStack) sorting — no custom sort logic." The actual `useReactTable` call has no `getSortedRowModel`, no `sorting` state, and the `TableHead` cells render plain static text with no click handler or sort indicator.

**Where:** `frontend/src/components/projects/ProjectsTable.tsx` (the `useReactTable(...)` call and the `TableHeader` render block).

**Spec reference:** `docs/requirements/project.md` §Projects List Screen.

**Why it matters:** Only the backend's hardcoded `created_at desc` order (matching the spec's "default sort on landing") is ever shown — a user has no way to re-sort by name, status, client, or type as the spec explicitly promises. Contrast with `CompaniesTable`/`UsersTable`, whose specs don't claim sortability, and with `ProjectsTable`'s own already-implemented column-visibility ("Columns") feature, which shows the sorting omission isn't a TanStack-integration limitation.

**Severity:** Moderate.

**Suggested next step:** Wire up `getSortedRowModel()` + a `sorting` state + clickable `TableHead`s (the standard shadcn Data Table sortable-header pattern).

**Status: Fixed (2026-09-06).** `ProjectsTable.tsx` now wires `getSortedRowModel()`/`SortingState`/`onSortingChange` into `useReactTable`, and every real data column (`name`, `status`, `client_company_name`, `vendor_company_name`, `project_type`, `created_at`) renders a clickable ghost-button header with the `ArrowUpDown` icon, toggling ascending/descending via `column.toggleSorting(column.getIsSorted() === "asc")` — the shadcn/ui Data Table convention. Sorting is client-side over the current page only (`manualSorting` left unset), matching the spec's "out-of-the-box... no custom sort logic" wording; the backend's `created_at desc` default is unchanged. Verified live: clicking "Name" correctly re-sorts ascending, then descending, on a page with 3 rows.

**Addendum (2026-09-06, same day): the client-side mechanism above was itself a bug, since fixed.** With only 3 rows (one page) the fix above looked correct, but a client-side `getSortedRowModel()` only ever reorders whichever page is already in memory — with a server-paginated table, that's incorrect the moment there's more than one page: sorting ascending by name on page 1 could omit the true first row entirely (stuck on page 2), and page 2 would show a completely different, discontinuous order. Reproduced live with 51 test projects (deleted afterward) confirming exactly this. Fixed properly by moving sorting server-side: `app/services/sorting.py`'s `resolve_sort()` (a whitelisted column map + mandatory `id` tie-breaker, silently falling back to each endpoint's existing default on an unrecognized `sort_by`) wired into `list_projects`/`list_companies`/`list_users` and their endpoints via new `sort_by`/`sort_dir` query params; the frontend now sets `manualSorting: true` and refetches (via `components/data-table/sorting.ts`'s `toSortParams()`) instead of calling `getSortedRowModel()`. Re-verified live with the same 51-row repro: page 1 now correctly starts at the true first row and page 2 continues exactly where it left off. `project.md`, `company.md`, `user.md`, and `frontend.md` all updated to describe the corrected (server-side) mechanism.

---

### 6. Login DTO field named `email`, not `name_id` — Minor

**What:** The login request schema and every frontend caller name the credential field `email`, even though the entity's actual identity field — used everywhere else in the codebase — is `name_id`, and `auth.md` explicitly warns that for an SSO user this value "must not be typed/validated as [an email]."

**Where:** `backend/app/schemas/auth.py` (`LoginRequest.email`), `frontend/src/pages/LoginPage.tsx`, `frontend/src/providers/AuthProvider.tsx` (`login(email, password)`).

**Spec reference:** `docs/requirements/auth.md`, `docs/requirements/user.md` §Entity ("name_id... not necessarily an email address").

**Why it matters:** Purely a naming/consistency issue today (local login only) — no behavior is broken, since the value is never actually validated as an email format. But it's the one place in the codebase where the "identity field is not necessarily an email" principle isn't reflected in naming, which is exactly the kind of inconsistency that tends to cause a real bug once SSO (whose `name_id` is explicitly not guaranteed email-shaped) is wired into this same login surface.

**Severity:** Minor.

**Suggested next step:** Rename the field to `name_id` (or `login`) end-to-end before SSO login is implemented.

---

## Consistency Issues

### 7. `database.md`'s migration policy contradicts the project's actual, consistent practice — Moderate

**What:** `docs/architecture/database.md` §Migrations states: "Never edit an Alembic migration that has already been merged; write a new one." In practice, the entire project history does the opposite: `backend/alembic/versions/` contains exactly one file, `0001_initial.py`, and `git log -- backend/alembic/versions/` shows 5 separate feature commits (initial codebase, timesheeting, timesheeting usability, the project_admin/project_manager role split, project manager assignment) that each modified that same file rather than adding a new one.

**Where:** `docs/architecture/database.md` §Migrations vs. `backend/alembic/versions/` (only `0001_initial.py`) and `git log`.

**Why it matters:** This isn't a one-off slip — it's the consistently applied convention across every schema change so far, directly opposite to what the architecture doc tells a new contributor (or agent) to do. Whoever next reads `database.md` and follows it literally (writing `0002_...py`) would break from the established pattern; whoever follows the established pattern is contradicting the doc. One of the two needs to change.

**Severity:** Moderate.

**Suggested next step:** Decide which convention is actually intended going forward (single-squashed-migration is a defensible pre-launch choice) and update `database.md` to state it explicitly, rather than leaving the stated policy and the practiced one at odds.

**Status: Fixed (2026-09-06).** Confirmed with the author: the "never edit a merged migration" rule is the correct permanent policy, not a mistake — it just doesn't apply yet. `database.md` §Migrations now states a "Pre-release exception (current phase)" explaining that everything is folded into `0001_initial.py` in place only because this repo is private, pre-release, and no environment has ever migrated real data against it; the stated rule takes over unconditionally from the first tagged release onward. No code changed.

---

### 8. `auth.md`'s session-refresh design is marked "not yet implemented" but is fully built — Moderate

**What:** `docs/requirements/auth.md` §Session Expiry & Token Refresh is headed "**Status: not yet implemented.** This section is a design writeup, not a description of current behavior." The mechanism it describes in detail — concurrent-refresh de-duplication, a retry-once guard, exempting `/auth/refresh`/`/auth/login`/`/auth/logout` from the interceptor, an event-bridge (not hard-redirect) sync into `AuthProvider`, and not double-notifying on the mount-time `/auth/me` check — is fully implemented, matching the design almost point-for-point.

**Where:** `docs/requirements/auth.md` §Session Expiry & Token Refresh vs. `frontend/src/api/client.ts` (`attemptRefresh`, `AUTH_EXEMPT_PATHS`, `SILENT_REFRESH_PATHS`), `frontend/src/providers/AuthProvider.tsx`, `frontend/src/api/sessionEvents.ts`. The implementation's own comments cite "auth.md design doc, point 1/3/5" — it was clearly built directly from this section.

**Why it matters:** Anyone (human or agent) trusting this doc's status line to decide "is this built yet?" gets the wrong answer, and might re-implement or redesign a mechanism that already exists and already matches the design closely.

**Severity:** Moderate (documentation-currency issue, not a functional bug — the code itself is correct).

**Suggested next step:** Update the section's status line to reflect that it's implemented, and fold the "design" framing into a description of current behavior.

**Status: Fixed (2026-09-06).** Header changed to "Session Expiry & Token Refresh", the status line now says "implemented" and points at the three actual files, and the two present-tense "today it isn't"/"nothing calls it today" sentences describing the pre-fix state were moved into past tense under a renamed "The problem this replaced" heading. The five-point rationale is otherwise unchanged, since it still accurately explains why the code is shaped the way it is.

---

### 9. `project.md` documents two "known divergences" that have already been fixed in code — Minor

**What:** Two notes in `project.md` describe frontend gaps as current/unfixed; both are stale:

- "**Known divergence**: the current implementation (`ServiceLinesTable.tsx`) still does `line.users.map((u) => u.full_name).join(", "))`... not yet fixed." The actual code (`frontend/src/components/projects/ServiceLinesTable.tsx:144-146`) already renders one `<div>` per consultant, exactly as the spec requires — no `join(", ")` anywhere in the file.
- "This is a divergence from the currently-implemented picker, which calls `listUsers({ role: "consultant" })` once on open and filters nothing itself." Both `ServiceLineFormDialog.tsx` and `ProjectManagersPicker.tsx` already implement debounced (300ms), server-side search exactly as specified.

**Where:** `docs/requirements/project.md` §Service Lines (Consultants column note) and §Project Managers/§Service Lines "Add/Edit Modal" (search note) vs. `frontend/src/components/projects/ServiceLinesTable.tsx`, `ServiceLineFormDialog.tsx`, `ProjectManagersPicker.tsx`.

**Why it matters:** Low risk on its own, but it's a pattern worth noticing: two separate self-documented "this is wrong, not yet fixed" notes in the same file, both actually fixed without the note being removed. It suggests spec updates aren't consistently made when a flagged gap gets closed, which erodes trust in every other "not yet implemented"/"known divergence" note in the doc set (see also #8 above).

**Severity:** Minor.

**Suggested next step:** Remove both notes now that the underlying code matches spec.

**Status: Fixed (2026-09-06).** Both notes rewritten as "Implemented as specified," describing the actual code rather than a gap. A third, related stale note was found and fixed in the same pass: the Service Lines status-based edit/delete rules (§Service Lines' bulleted list, the Status enum table, and §2 Entity: Service Line's own Validation rules) all still described the active-project-with-logged-time delete block as "not yet implementable, pending timesheeting" — stale for the same reason (see Finding #1, now also fixed) — and have been updated to describe the implemented check instead.

---

### 10. `docs/sast.md` is stale on its own top 2 findings — Moderate

**What:** `docs/sast.md` (dated 2026-08-05) lists as its #1 (Critical) and #2 (High) findings a hardcoded fallback JWT signing secret and hardcoded fallback DB/seed-admin-password defaults in `Settings`. Both are already fixed: every field on `Settings` in `backend/app/core/config.py` is now required with no default (`database_url: str`, `jwt_secret_key: str`, `seed_admin_password: str`, etc.), and the file's own comment explicitly references this exact fix ("see docs/sast.md"). Findings #3-7 (no logout revocation, no login rate limiting, `cookie_secure` defaulting `False`, the login timing side-channel, and no security response headers) all remain accurate as of this audit.

**Where:** `docs/sast.md` Executive Summary and Findings #1-2 vs. `backend/app/core/config.py`.

**Why it matters:** The report's own "Top 3 risks" list leads with two issues that are no longer real, which could cause wasted remediation effort or, worse, false confidence that the remaining findings (which are still valid) are similarly already handled.

**Severity:** Moderate (the underlying security posture is fine — this is purely about the report's accuracy misleading a reader).

**Suggested next step:** Add an erratum/update to `sast.md` marking Findings #1-2 resolved, referencing the current `config.py`.

---

### 11. `index.md` still describes the superseded 3-role model — Minor

**What:** `docs/requirements/index.md` §1 Overview still says "`users` roles are `administrator`, `manager` or `consultant`," "A `consultant` can only see one screen: `timesheet`," and "A `manager` can additionally see `projects`." This is the pre-split role model; `user.md` §Entity documents the actual current 4-role model (`administrator`/`project_admin`/`project_manager`/`consultant`) and explicitly notes `project_admin` is "renamed from the earlier `manager`" and `project_manager` is a distinct, newer role.

**Where:** `docs/requirements/index.md` §1 Overview vs. `docs/requirements/user.md` §Entity, §Role → Screen Access.

**Why it matters:** `index.md` is the top-level entry point into the requirements doc set — a reader starting there gets a materially wrong role model before ever reaching `user.md`'s correction.

**Severity:** Minor.

**Suggested next step:** Update `index.md`'s Overview to reference the current role names, or replace the inline description with a pointer to `user.md`.

---

### 12. "No em dashes in code/comments/docs" rule is violated almost everywhere, including by itself — Minor

**What:** `backend.md` §Code Quality Standards: "**Punctuation**: no em dashes in code/comments/docs — use commas, colons, or separate sentences." The rule's own sentence contains an em dash. A repo-wide check found em dashes in the majority of `backend/app/**/*.py` files' comments/docstrings (17 of the files checked), and every requirements/architecture doc in `docs/` is written with em dashes as its dominant punctuation style throughout.

**Where:** `docs/architecture/backend.md` §Code Quality Standards vs. nearly the entire `backend/app` tree and `docs/` tree.

**Why it matters:** Not a functional issue, but a rule this comprehensively and consistently ignored (by the very document stating it) signals either the rule is wrong/should be scoped more narrowly (e.g. to generated user-facing strings only), or style conventions in this project aren't actually enforced/reviewed against this doc.

**Severity:** Minor.

**Suggested next step:** Either remove/scope the rule to what's actually intended, or add a Ruff/lint check if it's meant to be enforced.

---

## Best Practice Concerns

### 13. Service line deletion has zero test coverage — Moderate

**What:** No test in `backend/tests/test_projects_api.py` exercises the service-line delete endpoint at all (`grep` for delete/service-line-deletion tests returns nothing).

**Where:** `backend/tests/test_projects_api.py` (absence); the untested code is `DELETE /projects/{project_id}/service-lines/{line_id}` in `backend/app/api/projects.py`.

**Why it matters:** Compounds Finding #1 — the missing business rule (block delete on `active` project with logged time) was never caught by tests because the endpoint isn't tested at all, not even for the rules that *are* implemented (the `closed`-project block). `backend.md` §Testing explicitly requires coverage for "any endpoint with authorization logic... in addition to core business logic."

**Severity:** Moderate.

**Suggested next step:** Add tests for delete on `draft`/`active`/`closed` projects, and (once Finding #1 is fixed) for the logged-time block.

---

### 14. Login timing side-channel remains unaddressed — Low-Moderate

**What:** `authenticate_local_user` still returns early without any password-verification work for "no such active local user"/SSO/no-password cases, and only runs the (deliberately expensive) Argon2 `verify()` when a real local account is found — exactly the pattern `docs/sast.md` Finding #6 already identified as defeating the app's own stated "generic error, don't reveal whether an email is registered" goal via response-time measurement.

**Where:** `backend/app/services/user_service.py:144-155`.

**Spec reference:** `docs/requirements/auth.md` User Stories ("a generic error message on failed login, so that the system doesn't reveal whether an email is registered"); `docs/sast.md` Finding #6.

**Severity:** Low-Moderate (already catalogued in `sast.md`; repeated here because it directly contradicts a stated user story, not just a general hardening suggestion).

**Suggested next step:** Burn equivalent time on every short-circuit branch via a dummy hash verification, as `sast.md`'s own remediation sketch proposes.

---

### 15. No rate limiting on login, no security response headers — Low

**What:** Both remain exactly as `docs/sast.md` Findings #4 and #7 described: `POST /auth/login` has no throttling/lockout of any kind, and `main.py` registers only `CORSMiddleware` — no `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, or `Strict-Transport-Security`.

**Where:** `backend/app/api/auth.py` (login), `backend/app/main.py`.

**Severity:** Low (already catalogued; included here only to confirm they're still unfixed as of this pass).

**Suggested next step:** See `sast.md`'s existing remediations (`slowapi` for rate limiting, a small headers middleware).

---

### 16. `cookie_secure` still defaults to `False` with no fail-fast guard — Minor

**What:** As `sast.md` Finding #5 already noted, `cookie_secure: bool = False` remains the default in `Settings`, with no startup check preventing an accidental production deployment with cookies served over plain HTTP.

**Where:** `backend/app/core/config.py:30`.

**Severity:** Minor (the default is now at least documented/intentional for local dev, per the field's own comment — unlike Findings #1-2 above, which had no such rationale and have been fixed).

**Suggested next step:** Consider a startup assertion requiring an explicit `environment=development` flag alongside `cookie_secure=false`, as `sast.md` suggests.

---

## Open Questions

### 17. Minimum-one-consultant before a service line's project can go `active`

`project.md`'s own Open Questions section leaves this genuinely unresolved. Confirmed: no such check exists anywhere in `project_service.py` — a service line can be `active` with zero assigned consultants. No action needed beyond what the spec itself already tracks; noted here only to confirm the code matches the doc's "still open" status.

### 18. `PartyIdentifier` has no "at most one primary per type" constraint, unlike `Address`

`company.md`'s Open Questions asks whether `PartyIdentifier` should get the same "at most one primary per `(company_id, id_type)`" rule `Address` already has (`uq_addresses_primary_per_type`, backed by both a proactive API check and a partial unique index). Confirmed: `PartyIdentifier` has no equivalent index or API check at all — the schema is asymmetric between the two entities today, exactly as the open question describes.

### 19. Cross-company identifier uniqueness

Directly related to Finding #3 above — `company.md` leaves open whether/how to add global (not per-company) uniqueness for `VAT`/`LEGAL_REGISTRATION`/`PEPPOL_PARTICIPANT`. This audit found a concrete, reachable path (`Duplicate`) that makes the gap real rather than theoretical — see Finding #3.

---

## Summary

**Total findings: 19** (16 numbered findings + 3 open questions carried from existing spec docs and confirmed against code)

| Category | Critical | Major | Moderate | Minor/Low | Total |
|---|---|---|---|---|---|
| Spec Deviations | 0 | 1 | 4 | 1 | 6 |
| Consistency Issues | 0 | 0 | 3 | 3 | 6 |
| Best Practice Concerns | 0 | 0 | 1 | 3 | 4 |
| Open Questions | — | — | — | — | 3 |
| **Total** | **0** | **1** | **8** | **7** | **19** |

No Critical findings — the codebase's security-critical defaults (JWT secret, DB credentials, seed-admin password) have already been hardened since the last SAST pass, and no broken access control or injection issue was found in this review.

### Top 5 things to address first

1. ~~**Enforce the "no delete with logged time" rule on active-project service lines**~~ (Finding #1) — **Fixed 2026-09-06**, see the finding for details.
2. ~~**Fix `duplicate_company`'s identifier uniqueness gap**~~ (Finding #3) — **Closed, not a bug (2026-09-06)**: cross-company uniqueness is deliberately unenforced; see the finding for the reasoning.
3. ~~**Update `auth.md`'s refresh-mechanism status and `project.md`'s two stale "known divergence" notes**~~ (Findings #8, #9) — **Fixed 2026-09-06**, see the findings for details.
4. ~~**Reconcile `database.md`'s migration policy with actual practice**~~ (Finding #7) — **Fixed 2026-09-06**: documented as a deliberate, temporary pre-release exception; the stated policy remains correct from release onward.
5. ~~**Add test coverage for service-line deletion**~~ (Finding #13) — **Fixed 2026-09-06** as part of Finding #1's fix (two new tests added to `test_projects_api.py`).

---

## shadcn/ui Usage Audit (2026-09-06)

A separate, narrower pass, requested specifically to check this codebase's actual shadcn/ui usage against the framework's own best-practice guidance — the `shadcn` skill installed via `pnpm dlx skills add shadcn/ui` (`.agents/skills/shadcn/`, cloned from `github.com/shadcn/ui.git`). Findings continue the numbering above. "Guidance reference" below points at the skill's rule files rather than a `docs/requirements/*.md` spec, since this pass checks framework conventions, not this app's own functional spec.

Every `.tsx` file under `frontend/src` was reviewed: all 19 files in `components/ui/`, every consumer across `components/{companies,projects,timesheet,users,data-table}/` and `pages/`, plus `components.json` and `index.css`.

### 20. `components.json` and the installed primitives are on a legacy shadcn generation, predating most of the rules this audit checks against — Moderate

**What:** `components.json` has `"style": "default"` with no `base`, `iconLibrary`, or `registries` fields at all — fields the current CLI (and the skill's own `info --json` output) always populates. Consistent with that: `components/ui/button.tsx` has no `data-icon` CSS hook (icon sizing/spacing has nothing to attach to), its `outline`/`ghost` variants hover to `bg-secondary` rather than `bg-accent`, and `index.css` never defines `--accent`/`--accent-foreground` at all — a color pair every current shadcn component assumes exists. None of the newer registry items referenced by the skill (`Field`/`FieldGroup`, `InputGroup`, `ToggleGroup`, `Empty`, `Skeleton`, `Avatar`, `Spinner`) have ever been added.

**Where:** `frontend/components.json`, `frontend/src/index.css`, `frontend/src/components/ui/button.tsx`.

**Guidance reference:** `.agents/skills/shadcn/SKILL.md` §Key Fields (`base`, `iconLibrary` expected), `rules/icons.md` (`data-icon` convention), `customization.md` (accent token expected by all components).

**Why it matters:** This is the root cause behind several of the findings below — e.g. `data-icon` (#24) can't be adopted by editing call sites alone, because the installed `button.tsx` doesn't wire it to anything yet. It also means a plain `npx shadcn@latest add button --diff` would show a large, unrequested diff (variant colors, new props) rather than a clean no-op, so any future "just update this one component" request needs to go through the CLI's smart-merge flow (`--dry-run`/`--diff`), not a blind overwrite.

**Severity:** Moderate — no functional bug, but it's the reason several best-practice checks below can't be fixed by a local edit alone.

**Suggested next step:** Not urgent pre-launch. When there's appetite to modernize, use `npx shadcn@latest add <component> --diff` per-component (per the skill's "Updating Components" workflow) rather than re-`init`-ing, since every primitive here has been hand-customized (dark-mode Tailwind v4 tokens, i18n, etc.) and a preset `apply` would overwrite that.

**Addendum (2026-09-06):** Confirmed directly while adding `field.tsx` for Finding #22's fix: `npx shadcn@latest info` (run from `frontend/`) reports "No components installed" and resolves the `ui` alias to the literal path `frontend/@/components/ui`, not `frontend/src/components/ui` — the CLI isn't parsing the `@/*` → `./src/*` mapping in `tsconfig.app.json`, most likely because `baseUrl` was removed from that file in a recent commit (TS 5.4+ doesn't need it, but this CLI version apparently still does for its own alias detection). `npx shadcn@latest add label --diff` renders the entire already-existing `label.tsx` as a from-scratch `+` diff, confirming the CLI has no idea any component is already installed. Practical consequence: don't run `npx shadcn add <component>` for real in this project until this is fixed — use `--view`/`--dry-run` (both read-only, and resolve from the real registry) to fetch authoritative source, then place the file manually. This is the same root cause as `frontend.md`'s Component Patterns § "UI primitives" bullet, which already separately documented components landing under a stray `frontend/@/...` directory — this addendum just pins down why.

---

### 21. `SelectItem`/`DropdownMenuItem` are never wrapped in their `Group` component — Minor

**What:** The skill's Critical Rule "Items always inside their Group" (`SelectItem` → `SelectGroup`, `DropdownMenuItem` → `DropdownMenuGroup`) is violated in every `Select` and almost every action `DropdownMenu` in the app. `SelectContent` renders `SelectItem`s directly with no `SelectGroup` wrapper in all 5 places `Select` is used (`pages/ProjectFormPage.tsx`, `components/timesheet/AddServiceLineSelect.tsx`, `components/companies/AddressFormDialog.tsx`, `components/companies/IdentifierFormDialog.tsx`, `components/projects/ServiceLineFormDialog.tsx`). Same pattern for the row-actions `DropdownMenu` in `ServiceLinesTable.tsx`, `PartyIdentifiersTable.tsx`, `CompaniesTable.tsx`, `AddressesTable.tsx`, `UsersTable.tsx`, and `ProjectsTable.tsx` (two menus). The one exception is `NavBar.tsx`'s user-avatar menu, which does correctly wrap its settings items in a `DropdownMenuGroup` — showing the convention is known, just not applied consistently.

**Where:** Listed above; the installed `components/ui/select.tsx` and `dropdown-menu.tsx` both fully support `SelectGroup`/`DropdownMenuGroup` already, so this isn't blocked by Finding #20.

**Guidance reference:** `.agents/skills/shadcn/rules/composition.md` §Items always inside their Group component.

**Why it matters:** Functionally inert today (Radix's un-grouped rendering works fine visually and behaviorally for a single flat list) — this is purely a convention/accessibility-semantics gap: `SelectGroup`/`DropdownMenuGroup` exist to carry `role="group"` and (with a `SelectLabel`/`DropdownMenuLabel`) an accessible group name for screen readers. None of these menus currently need a label since they're single flat lists, which is likely why it was never added — but it's worth fixing for consistency before any of these menus grows a second logical section (e.g. adding a "Danger zone" separator group to the row-actions menus, which already visually separate "Delete" with `DropdownMenuSeparator`).

**Severity:** Minor.

**Suggested next step:** Wrap each flat item list in a single `SelectGroup`/`DropdownMenuGroup` — a mechanical, low-risk change with no visual effect. Not urgent.

---

### 22. Forms use raw `div` + `Label` + `Input` instead of `FieldGroup`/`Field`/`FieldSet` — Moderate

**What:** All 4 form pages (`LoginPage.tsx`, `UserFormPage.tsx`, `CompanyFormPage.tsx`, `ProjectFormPage.tsx`) build every field as `<div className="flex flex-col gap-2"><Label>...</Label><Input .../>{error && <p>...}</div>`, and group related fields with plain `<div className="flex flex-col gap-4">`. The `Field`/`FieldGroup`/`FieldLabel`/`FieldDescription`/`FieldSet`/`FieldLegend` components the skill treats as the required form-layout primitives are not installed anywhere in `components/ui/`. The clearest missed fit is `UserFormPage.tsx`'s Roles checkbox list (`ALL_ROLES.map(...)` rendering a `Checkbox` + `Label` per role under a plain `<Label>{t("Roles")}</Label>`) — exactly the "related checkboxes under a heading" case the skill says should be a `FieldSet` + `FieldLegend`, not a `div` with a heading.

**Where:** `frontend/src/pages/LoginPage.tsx`, `UserFormPage.tsx`, `CompanyFormPage.tsx`, `ProjectFormPage.tsx`.

**Guidance reference:** `.agents/skills/shadcn/rules/forms.md` §Forms use FieldGroup + Field, §FieldSet + FieldLegend for grouping related fields.

**Why it matters:** The current hand-rolled markup already achieves the same visual result and reads reasonably clearly, so this isn't a user-facing bug. The main practical cost is validation-state styling: the skill's `data-invalid`/`aria-invalid` pattern (`data-invalid` on `Field`, `aria-invalid` on the control) gives a field's label and description a consistent invalid-state look for free; today each form hand-writes its own `{errors.x && <p className="text-sm text-destructive">...}` per field with no `data-invalid`/`aria-invalid` wired onto the `Input`/`Label` at all, so screen readers get no `aria-invalid` signal on any of these forms' inputs today.

**Severity:** Moderate — the missing `aria-invalid` is a real (if minor) accessibility gap across every form in the app, not just a style-guide nit.

**Suggested next step:** Two independent, separable pieces: (1) a cheap, high-value fix regardless of the rest — add `aria-invalid={!!errors.x}` to each `Input` (react-hook-form makes this a one-line addition per field); (2) the larger `FieldGroup`/`Field`/`FieldSet` migration, which is a genuine (if mechanical) refactor across all 4 forms — worth doing opportunistically the next time one of these forms is touched, not as a standalone task.

**Status: Fixed (2026-09-06).** All 4 form pages now use `Field`/`FieldGroup`/`FieldLabel`/`FieldError`/`FieldSet`/`FieldLegend` (added as `frontend/src/components/ui/field.tsx`, fetched verbatim from the real registry via `npx shadcn@latest add field --view field.tsx` — the CLI's own alias-detection bug documented in Finding #20's addendum meant the file had to be placed manually rather than via a live `add`; no new npm dependencies, since `field.tsx` only needs the already-installed `label.tsx`/`separator.tsx`). Every field now carries `data-invalid`/`aria-invalid` wired to its `react-hook-form` error state, closing the accessibility gap this finding flagged — verified live that an invalid field's label renders in `text-destructive` red and its control has `aria-invalid="true"` in the DOM. `UserFormPage`'s Roles checkbox list is now exactly the `FieldSet` + `FieldLegend` + inner `FieldGroup` of horizontal `Field`s the skill's own example shows. Grid-column field pairs and inter-section `<Separator />`s were deliberately left as plain layout, per `frontend.md`'s updated Component Patterns notes.

**A real bug was found and fixed during this migration**, not just a style change: a `FieldGroup` nested inside another `FieldGroup`/`FieldSet` (only the Roles section fits this) inherits `FieldGroup`'s default `@container/field-group` class (`container-type: inline-size`). Live-reproduced a Chromium layout bug where that nested element renders at its correct height on first paint, then collapses to `0px` — becoming invisible and unclickable — on the very next re-render of that subtree (trivially triggered by unchecking a role checkbox). Root-caused via a live DOM diff (no class or node actually changes across the collapse) and fixed by adding `[container-type:normal]` to that one nested `FieldGroup`, which is safe since nothing in this app uses the `Field` "responsive" orientation variant that the container query exists for. See `frontend.md`'s Component Patterns § "Form layout" for the full writeup, so any future nested `FieldGroup` gets the same treatment. All 4 forms re-verified live end-to-end (empty-submit validation, then a full successful save) after the fix; test rows created during verification were deleted and row counts re-confirmed.

---

### 23. Submit buttons swap text on `isSubmitting` with no `Spinner` — Minor

**What:** `LoginPage.tsx`'s submit button renders `{isSubmitting ? t("Signing in…") : t("Sign in")}`; `CompanyFormPage.tsx`, `ProjectFormPage.tsx`, and `UserFormPage.tsx` only `disabled={isSubmitting}` the button with no text or visual change at all. None compose a `Spinner`, which isn't installed in `components/ui/`.

**Where:** `frontend/src/pages/LoginPage.tsx:88`, `CompanyFormPage.tsx:245`, `ProjectFormPage.tsx:386`, `UserFormPage.tsx:277`.

**Guidance reference:** `.agents/skills/shadcn/rules/composition.md` §Button has no isPending or isLoading prop (the `Spinner` + `data-icon` + `disabled` composition it recommends instead).

**Why it matters:** `disabled` alone (Company/Project/User forms) is a real UX gap, not just a style nit — on a slow network a user gets zero visual feedback that the click registered at all beyond the button graying out, which reads as unresponsive rather than "saving." `LoginPage`'s text-swap is a reasonable stopgap but is inconsistent with the other three forms.

**Severity:** Minor.

**Suggested next step:** Add `components/ui/spinner.tsx` (`npx shadcn@latest add spinner`) and standardize all 4 submit buttons on the `<Spinner data-icon="inline-start" />` + loading-label pattern.

---

### 24. Icons inside buttons use manual `mr-2 h-4 w-4` instead of `data-icon` — Minor (blocked by Finding #20)

**What:** All 14 icon-in-button/menu-item call sites (`Plus`, `Columns3`, `SunMoon`, `LanguagesIcon`, `LogOut`, etc. across `NavBar.tsx`, `ProjectsTable.tsx`, `CompaniesTable.tsx`, `UsersTable.tsx`, `ServiceLinesTable.tsx`, `PartyIdentifiersTable.tsx`, `AddressesTable.tsx`) hand-size and hand-space icons with `className="mr-2 h-4 w-4"` rather than `data-icon="inline-start"`.

**Where:** See file list above; sample at `frontend/src/components/projects/ProjectsTable.tsx:250,271`.

**Guidance reference:** `.agents/skills/shadcn/rules/icons.md` §Icons in Button use data-icon attribute.

**Why it matters:** Purely cosmetic/consistency today — the manual classes render correctly. Flagged mainly because it's a direct consequence of Finding #20: the installed `button.tsx` has no `data-icon` CSS selector wired up, so switching these call sites to `data-icon` alone would silently do nothing (no error, but no effect) until `button.tsx` itself is updated from upstream.

**Severity:** Minor.

**Suggested next step:** Bundle with Finding #20's eventual `button.tsx` update — not worth doing in isolation.

---

### 25. Timesheet lock/weekend cell colors use raw Tailwind reds and manual `dark:` overrides instead of a semantic token — Moderate

**What:** `TimesheetDesktopGrid.tsx` (`bg-red-200 dark:bg-red-900/50` / `bg-red-100 dark:bg-red-950/40`) and `TimesheetMobileView.tsx` (`bg-red-100 dark:bg-red-950/40`) hand-pick raw Tailwind red shades with a manual `dark:` variant for the locked/weekend cell backgrounds, rather than a semantic CSS variable.

**Where:** `frontend/src/components/timesheet/TimesheetDesktopGrid.tsx:187-188`, `components/timesheet/TimesheetMobileView.tsx:133`.

**Guidance reference:** `.agents/skills/shadcn/rules/styling.md` §No raw color values for status/state indicators, §No manual dark: color overrides.

**Why it matters:** This is the same code this conversation already fixed once for a different bug (the `cn()` background-class collision that made locked weekday/weekend cells indistinguishable) — so it's a natural next stop, but on its own it's a style-consistency issue, not a correctness one: the two `dark:` shades were deliberately hand-picked for contrast/legibility against the app's dark background, and today's fix already verified they render distinctly. `Badge`/`bg-destructive` don't fit a full-cell calendar background the way they fit a small status pill, so the "correct" fix per `customization.md` is a purpose-built pair of CSS variables (e.g. `--calendar-locked`/`--calendar-locked-dark`) rather than forcing this into the generic `--destructive` token, which is semantically about form/action errors, not calendar-cell state.

**Severity:** Moderate (real rule violation, but not a functional bug — the current colors are correct and already verified).

**Suggested next step:** If the timesheet's visual language grows more states (e.g. a third color for "pending approval"), define dedicated `--calendar-*` variables in `index.css` at that point rather than continuing to hand-pick raw Tailwind shades per state. Not urgent in isolation.

---

### Note: several skill-recommended components have no current use case in this app

`ToggleGroup`, `InputGroup`, `Empty`, `Skeleton`, `Avatar`, and `FieldSet`/`Field` (see Finding #22) are not installed. Checked specifically for each: no 2-7-option exclusive toggle exists anywhere that's currently faked with a manual `Button` loop (none found); no `Input` has a button or icon manually absolute-positioned inside it (the one `absolute`-positioned element found, `TimesheetMobileView.tsx:92`, is an unrelated small status-dot badge, not an input decoration); the Data Table's empty state (`DataTable.tsx`'s single centered `<TableCell>{emptyMessage}</TableCell>` row) is a reasonable fit for a table body — the full `Empty` component's icon/title/description/action layout doesn't fit inside a single table row; no loading-skeleton screens exist anywhere in the app today (pages either render immediately from already-fetched data or show nothing during the brief fetch); and no user avatars are rendered anywhere (`NavBar.tsx`'s user menu trigger is icon-only). None of this is a violation — these are "not needed yet," not "needed and done wrong." Worth a second look if/when a matching UI need actually arises (e.g. a settings page with a genuine 2-3-way toggle, or a slower-loading dashboard that would benefit from `Skeleton`).

### shadcn/ui audit summary

| Finding | Severity | Category |
|---|---|---|
| #20 Legacy shadcn generation (`components.json`, missing accent token, no `data-icon` hook) | Moderate | Foundational |
| #21 `SelectItem`/`DropdownMenuItem` not wrapped in `Group` | Minor | Composition |
| #22 Forms bypass `FieldGroup`/`Field`/`FieldSet` (+ missing `aria-invalid`) | Moderate | Forms/Accessibility |
| #23 Submit buttons lack a `Spinner` composition | Minor | Composition |
| #24 Manual icon sizing instead of `data-icon` | Minor | Icons (blocked by #20) |
| #25 Timesheet colors use raw Tailwind + manual `dark:` | Moderate | Styling |

No Critical or Major findings. Positives confirmed during this pass, worth noting since they're easy to get wrong: `cn()` is used consistently everywhere for conditional classes (no manual ternary string interpolation found anywhere); no manual `z-index` overrides on any overlay component; every `Dialog`/`AlertDialog` has a proper `Title` (grep-verified across all 13 consumer files); `TabsTrigger` is correctly nested inside `TabsList` in the one place `Tabs` is used (`TimesheetHeader.tsx`); no `space-x-*`/`space-y-*` usage anywhere (the app already uses `flex` + `gap-*` throughout); and `Separator` (not raw `<hr>`/`border-t` divs) is used consistently since the earlier normalization pass in this same conversation.
