# Frontend Architecture — Vite + React + shadcn/ui

Component structure, state management, and styling rules. See also: [Backend](backend.md).

## Core Dependencies

Authorized frontend dependencies (per the Dependency Policy in [AGENTS.md](../../AGENTS.md)):

- `react`, `react-dom`, `typescript`, `vite` — base SPA toolchain
- `@types/node` — type declarations for Node built-ins (`node:path`, `__dirname`) used in
  `vite.config.ts`
- `tailwindcss`, `@tailwindcss/vite` — styling (Tailwind v4, CSS-first config via
  `src/index.css`'s `@theme inline` block; no `tailwind.config.ts`)
- shadcn/ui primitives (copy-in via CLI) and their support libs: `class-variance-authority`,
  `clsx`, `tailwind-merge`, `lucide-react`, `@radix-ui/*` (as pulled in per component)
- `react-router-dom` — client-side routing
- `react-hook-form`, `zod`, `@hookform/resolvers` — form state and validation
- `@tanstack/react-table` (v9 — `useTable`/`tableFeatures()`, not the v8 `useReactTable` API;
  see [Component Patterns](#component-patterns) below) — powers shadcn/ui's Data Table pattern.
  **Resolved, correcting an earlier version of this line**: search is *not* TanStack's native
  column filter — it's a debounced call to the backend's own `search` query param (see
  [company.md](../requirements/company.md#companies-list-screen)), since every list here is
  server-paginated and a client-side text filter can only ever see the current page's rows. This
  app registers exactly three features (`rowSortingFeature`, `rowPaginationFeature`,
  `columnVisibilityFeature` — see `components/data-table/features.ts`) and no
  `columnFilteringFeature` at all.
- `react-i18next`, `i18next`, `i18next-http-backend` — internationalization; the backend
  loads namespace JSON files from `public/locales` at runtime (not bundled) — see
  [Internationalization (i18n)](#internationalization-i18n) below
- `sonner` — shadcn/ui's `Sonner` toast component (the maintained replacement for the
  deprecated shadcn `Toast`/`useToast` primitive) — see
  [User Feedback (Toasts)](#user-feedback-toasts) below
- `cmdk` — powers shadcn/ui's `Command` palette component; paired with the `Popover` primitive
  (already covered by the blanket `@radix-ui/*` entry above) for searchable multi-select
  pickers — e.g. the Service Line `Consultants` field, see
  [project.md](../requirements/project.md#service-lines)
- `tw-animate-css` — the enter/exit animation utilities (`animate-in`/`animate-out`, `fade-*`,
  `zoom-*`, `slide-*`) that shadcn/ui's canonical component source references. Imported via
  `@import "tw-animate-css";` in `src/index.css`. **Not** `tailwindcss-animate` — that was the
  v3-era JS-plugin equivalent; this project is on Tailwind v4, which `tw-animate-css` requires
  (its own `package.json` says so; it ships `@theme`/`@utility` CSS that v3's engine can't
  parse). Both generate identical utility class names, so no component changes were needed when
  this project migrated from v3 to v4.
- `@zxcvbn-ts/core`, `@zxcvbn-ts/language-common`, `@zxcvbn-ts/language-en` — password strength
  scoring (0–4) for the live strength meter under any password-entry field — see
  [user.md § Password Policy](../requirements/user.md#password-policy). **Not** the original
  `zxcvbn` package — unmaintained since 2022; `@zxcvbn-ts/core` is the actively-maintained
  TypeScript rewrite with the same `score` (0–4) API.

## Mobile-First

- Design and implement for the smallest viewport first, then progressively enhance with
  Tailwind's responsive breakpoints (`sm:`, `md:`, `lg:`) — do not design desktop-first and
  retrofit mobile
- Touch targets, spacing, and typography should be validated at mobile widths before wider ones

## Code Quality

- **Linting**: ESLint
- **Formatting**: Prettier with the Tailwind CSS plugin (class sorting)
- **Type safety**: TypeScript strict mode; avoid `any` — use proper types or `unknown` + narrowing

## Component Patterns

- **App navigation shell**: a persistent, icon-only nav bar (vertical on desktop/left, bottom
  bar on mobile), role-gated per user — this is a product requirement, not just styling; see
  [home.md](../requirements/home.md#navigation) for the full requirement instead of duplicating
  it here.
- **Nav bar icon buttons share one style**: every icon button in the nav bar (screen icons and
  the profile icon) uses the same shared class/style definition — never style one ad hoc.
  Resting, hover, and active states must be identical across all of them (see
  `frontend/src/components/NavBar.tsx`'s `navIconClass`, and the requirement in
  [home.md](../requirements/home.md#navigation)). Prefer a static class over a per-item
  conditional/function (e.g. drive the active state off the `aria-current` NavLink already
  sets, via Tailwind's `aria-[current=page]:` variant, rather than branching in JS) — it keeps
  every icon's styling mechanism structurally identical, not just visually similar.
- **Data Table shell**: every paginated Data Table (Projects, Companies, Users) shares four
  files under `frontend/src/components/data-table/` rather than each hand-rolling its own
  `useTable` render/pagination JSX:
  - `features.ts` — the one `tableFeatures({ rowSortingFeature, rowPaginationFeature,
    columnVisibilityFeature })` object every table passes to `useTable`. No
    `columnFilteringFeature` (search is custom, not TanStack's), and deliberately no
    `sortedRowModel`/`paginatedRowModel` slots for the two features that do get registered —
    every table sets `manualSorting`/`manualPagination`, so the server has already sorted and
    paginated `data` before it reaches the table; the feature is registered purely for its
    column/table APIs and state, matching TanStack's own "server owns processing" pattern for
    manual features (confirmed against the v9 package's own bundled
    `skills/client-vs-server/SKILL.md`, not assumed).
  - `DataTable` — the header/body/empty-state table shell.
  - `DataTableColumnHeader` — a sortable-column header cell. Clicking it directly toggles
    ascending/descending, showing the current direction via an `ArrowUp`/`ArrowDown` icon or
    `ChevronsUpDown` when unsorted — no intermediate menu, matching the convention most data
    tables use, not the Asc/Desc/Hide dropdown shadcn's own
    `components/data-table-column-header.tsx` template at
    https://ui.shadcn.com/docs/components/aria/data-table shows. Column-hiding, where a table
    has any, stays reachable via that table's own toolbar "Columns" button instead.
  - `DataTablePagination` — the Previous/Next footer.
  - `sorting.ts`'s `toSortParams()` — translates `SortingState` into `sort_by`/`sort_dir` query
    params (see [Projects List Screen § API contract: sorting](../requirements/project.md
    #api-contract-sorting) for the backend side: the sortable-column whitelist and the mandatory
    `id` tie-breaker).

  These live under `components/data-table/`, not `components/ui/`, because (aside from
  `features.ts`) they're template/example code per shadcn's own docs (no `npx shadcn add` entry
  exists for them), not a swappable CLI-managed primitive. Each table still owns its own
  `useTable` call (column defs, search debounce, row-action dropdowns) — only the repeated
  shell/pagination markup, the sortable-header pattern, and the feature registration are shared.

  **Sorting and pagination are both server-side**, same as search (a debounced call to the
  backend's own `search` param, never TanStack's column filter — that's why
  `columnFilteringFeature` isn't registered at all): a sort-target/direction change resets to
  page 1, same as a search change. Sorting was originally implemented as a client-side
  `getSortedRowModel()` over just the current page — which looked correct with one page of dev
  data, but silently produced the wrong order the moment a table had more than one page, since
  it only ever reordered whatever 50 rows happened to already be in memory. TanStack's native
  filter/pagination/sorting row-models all operate on already-loaded rows and can't replace a
  paginated backend query, which is why none of the three get a row-model slot here.

  **On the v9 migration itself** (this was originally built against TanStack Table v8's
  `useReactTable`): the migration was done against v9's real `useTable`/`tableFeatures()` API,
  not the official `useLegacyTable` v8-compatibility shim (`@tanstack/react-table/legacy`) —
  that shim is deprecated and explicitly documented, in the package's own bundled migration
  guide, as "must not become the target architecture." Landing on it would have swapped one
  form of tech debt (an old major version) for another (a deprecated shim inside the new one)
  without actually adopting v9's model. Verified via the real installed package's type
  declarations and its bundled `skills/migrate-v8-to-v9/SKILL.md`, not a secondhand summary.
- **UI primitives**: shadcn/ui components (`frontend/src/components/ui/`) — customize via the
  shadcn CLI/copy-in pattern, don't fork behavior with ad-hoc wrapper hacks.
  **CRITICAL — always add new primitives via the real CLI** (`npx shadcn@latest add <component>`
  from `frontend/`, using the project's existing `components.json`), never by hand-writing a
  component's source from memory, even when it "should" just be a copy of a well-known pattern.
  Hand-typing silently drifts from the canonical output in ways that are easy to miss — real
  gaps found this way in this codebase: `Select` missing its scroll-up/down buttons and using
  `overflow-hidden` instead of `overflow-y-auto` (long option lists could get clipped with no
  way to reach the rest), `Button` missing the `secondary`/`link` variants and `icon` size,
  `Checkbox` with no `disabled:`/`focus-visible:` styling, `DropdownMenu`'s `SubTrigger` missing
  its submenu chevron. If the CLI genuinely can't be run in a given environment, treat any
  hand-written primitive as provisional and diff it against the real CLI output at the first
  opportunity (`npx shadcn@latest add <component> --overwrite` into a scratch directory, then
  `diff` against the real file) rather than trusting it indefinitely.
  **After running the CLI**, still review the output before trusting it as-is — two known,
  recurring gaps in this project: (1) new files can land under a literal `frontend/@/...`
  directory instead of `src/...` if the CLI's alias resolution misfires — check `git status`/
  `ls` for a stray `@/` folder after every `add` and move the files if so; (2) this project's
  CSS variables (`src/index.css`) deliberately don't define `--popover`/`--popover-foreground`
  or `--accent`/`--accent-foreground` — upstream shadcn output referencing `bg-popover`/
  `text-popover-foreground` must be changed to `bg-card`/`text-card-foreground`, and
  `bg-accent`/`text-accent-foreground` (usually a hover/selected state) to `focus:bg-secondary`
  or `data-[selected=true]:bg-secondary` — matching the substitution already applied in
  `select.tsx`/`dropdown-menu.tsx`/`popover.tsx`/`command.tsx`. Using the undefined tokens as-is
  doesn't error; the utility class just generates no CSS, so the surface silently renders
  transparent — easy to miss without actually opening the component in a browser.
- **Form layout**: every form (`LoginPage`, `UserFormPage`, `CompanyFormPage`, `ProjectFormPage`)
  uses shadcn's `Field`/`FieldGroup`/`FieldSet` primitives
  (`frontend/src/components/ui/field.tsx`) instead of hand-rolled `div`+`Label`+`Input` markup:
  - A single field is `<Field data-invalid={!!errors.x}><FieldLabel htmlFor="x">...</FieldLabel>
    <Input id="x" aria-invalid={!!errors.x} {...register("x")} /><FieldError
    errors={errors.x && [errors.x]} /></Field>` — `data-invalid` on `Field` drives its built-in
    red label/description styling, `aria-invalid` on the control is the actual accessibility
    signal (this project's older-generation `input.tsx`/`select.tsx` don't add their own visual
    `aria-invalid:` border styling — see the "UI primitives" bullet below on the CLI/preset gap —
    so the red `FieldLabel` text is the only visual invalid-state cue today, which is why both
    attributes matter and neither alone is enough).
  - A checkbox/switch row is `<Field orientation="horizontal">` wrapping the control and its
    `FieldLabel`. A related group of checkboxes (e.g. `UserFormPage`'s Roles) is a `FieldSet` +
    `FieldLegend` wrapping an inner `FieldGroup` of horizontal `Field`s, not a `div` with a
    heading.
  - Side-by-side field pairs keep a plain `grid grid-cols-1 sm:grid-cols-2 gap-4` wrapper around
    two `Field`s — that's a responsive-columns layout concern, not something `FieldGroup`'s own
    vertical-stack semantics replace. Separators between a form's fields and an unrelated section
    (e.g. `CompanyFormPage`'s Party Identifiers/Addresses tables) stay plain `<Separator />`, not
    `FieldSeparator` (that component is for dividing items *within* one `FieldGroup`).
  - **Known gotcha — a `FieldGroup` nested inside another `FieldGroup`/`FieldSet` must disable
    its own container query** (`className="... [container-type:normal]"`, as done for the Roles
    `FieldGroup` in `UserFormPage`). `FieldGroup`'s default class always includes `@container/
    field-group` (`container-type: inline-size`) — needed only for the `Field` "responsive"
    orientation variant, which nothing in this app currently uses. Left enabled on a *nested*
    FieldGroup, it triggers a real Chromium layout bug: the element renders at its correct height
    on first paint, then collapses to `0px` (and becomes unclickable) on the very next re-render
    of that subtree — reproduced live by simply unchecking a Roles checkbox. Confirmed via a
    live DOM diff that no class or DOM node actually changes across the collapse, and that
    setting `container-type: normal` is what fixes it (`flex-shrink: 0` does not) — so treat any
    future nested `FieldGroup` the same way unless it actually needs the responsive variant.
- **Styling**: TailwindCSS with the `cn()` utility for conditional class merging
- **State management**: React hooks (`useState`, `useEffect`, `useCallback`, `useMemo`); reach
  for a dedicated state library only when prop-drilling/hook composition actually breaks down
- **Data fetching**: a dedicated hooks layer (e.g. TanStack Query) with explicit loading/error
  states — no unhandled fetch promises in components

## Destructive Actions

- **Core rule**: any destructive action (delete, deactivate, remove, revoke, etc.) must show a
  confirmation dialog before executing — never fire immediately on click/select. This applies
  regardless of whether the underlying operation is a hard delete or a soft-delete/deactivation
  (e.g. a company's `Delete` action, which sets `is_active = false` — see
  [company.md](../requirements/company.md) — still reads as "delete" to the user and still
  needs confirmation).
- Use Radix's `AlertDialog` primitive (`@radix-ui/react-alert-dialog`, already covered by the
  blanket `@radix-ui/*` entry in Core Dependencies above) for this — it's purpose-built for
  confirmations (no dismiss-by-clicking-outside, unlike a regular `Dialog`) — not a bespoke
  modal or `window.confirm()` per feature.
- The confirmation should name the specific item being acted on (e.g. "Delete Acme
  Manufacturing SA?"), not a generic "Are you sure?".

## User Feedback (Toasts)

- **Core rule**: any action that mutates a record must confirm success to the user via a toast
  notification **unless the result is already immediately, unambiguously visible in the view the
  user is still looking at**. The rule exists for the specific failure mode of a `Save` button
  that leaves the form sitting there looking exactly like it did before — the user has no way to
  tell whether anything happened. It is not a blanket "toast every mutation" rule.
- Use shadcn/ui's `Sonner` component (`sonner` — see Core Dependencies above), not a bespoke
  banner, inline flash message, or `alert()`.
- **Wording**: short, specific, past tense, names what happened — e.g. "Project saved",
  "Acme Manufacturing SA deleted" — not a generic "Success!" or "Done."
- **Scope — required**: the `Save` action on a top-level record form — `CompanyFormPage`,
  `ProjectFormPage`, and their equivalents for future features — for both create and edit. Also
  the top-level list screens' row actions, `Duplicate` and `Delete`/`Deactivate` (e.g.
  `CompaniesTable`, `ProjectsTable`), since `Duplicate` navigates to a new form whose content
  looks identical to any other edit form (nothing marks it "this just got created"), and a
  destructive action's success is worth confirming explicitly rather than relying solely on a
  row disappearing.
- **Scope — not required**: child-entity CRUD inside a parent form's own Data Table — Company's
  `PartyIdentifiersTable`/`IdentifierFormDialog` and `AddressesTable`/`AddressFormDialog`,
  Project's `ServiceLinesTable`/`ServiceLineFormDialog`. Add/Edit/Delete there closes a modal
  back onto a table the user is already looking at, and the row immediately appears, updates, or
  disappears in it — that in-view change *is* the feedback, no toast needed on top of it. Same
  reasoning covers toggling the dark-mode radio button (the theme visibly changes right there), a
  login/logout redirect (arriving at a new screen is itself the confirmation), and a
  live/optimistic editing surface where toasting every keystroke would be noise (see the
  timesheet grid's own no-confirmation-dialogs rule in
  [timesheet.md](../requirements/timesheet.md) — same principle). Don't toast something the user
  can already see happened.
- **Errors**: keep using this app's existing inline error-message pattern (a
  `<p className="text-destructive">` near the triggering form/action) as the primary error
  surface — don't replace it with a toast. An error toast is optional on top of that, useful
  mainly for actions with no nearby place to show inline text (e.g. a background save that fails
  after its triggering dialog has already closed).

## Theming (Dark Mode)

- **Mechanism**: Tailwind's class-based dark mode, via `@custom-variant dark (&:is(.dark *));` in
  `src/index.css` (the v4 CSS-first equivalent of v3's `darkMode: ["class"]` — there is no
  `tailwind.config.ts` in this project) — a `dark` class toggled on the document root switches
  the CSS variable values already defined for both themes in `src/index.css`.
- **Values**: `light`, `dark`, `system` (default `system`) — see
  [home.md](../requirements/home.md#appearance) for the full requirement instead of duplicating
  it here.
- **`system` resolution**: via `window.matchMedia("(prefers-color-scheme: dark)")`, re-evaluated
  live if the OS setting changes while `system` is selected.
- **Persistence**: the preference is stored server-side on the user (see
  [database.md](database.md)), not just in browser storage — hydrate it from `/auth/me` on
  login, and send updates back through the users API. No new dependency needed (e.g. no
  `next-themes`) — implement as a small `ThemeProvider`/`useTheme` pair, same pattern as
  `AuthProvider`/`useAuth`.
- **Before login**: no persisted preference to read yet, so pre-auth screens (e.g. the login
  page) always follow `system`.

## Internationalization (i18n)

- **CRITICAL**: never write user-facing strings directly in components.
- **Always use `react-i18next`**: import and use the `t()` function.

  ```tsx
  import { useTranslation } from "react-i18next";

  function MyComponent() {
    const { t } = useTranslation(["timesheet"]);
    return <div>{t("Timesheet")}</div>;
  }
  ```

- **Translation files**: add English strings to the appropriate JSON files in
  `frontend/public/locales/en`.
- **Namespaces**: organize translations by requirement feature epic (e.g. `auth`, `company`,
  `home`). Use a `common` namespace when a translation doesn't fit a particular feature —
  generic actions/states reused across features (`Save`, `Delete`, `Cancel`, `Active`, …)
  belong there, not duplicated per namespace.
- **Key convention**: the key is the literal English source string (as in the example above),
  not a semantic dotted key — matches the source directly, so a missing/not-yet-loaded
  translation still renders something readable. The one exception is pluralized keys, which need
  i18next's `_one`/`_other` suffixes (e.g. `companyCount_one` / `companyCount_other`) since a
  count-dependent string can't itself be a fixed key.
- **Values outside component render** (Zod schema error messages, module-level label maps,
  etc.) can't call the `useTranslation()` hook. Build schemas that need translated messages
  inside the component (e.g. via `useMemo(() => z.object({...}), [t])`) rather than at module
  scope; for label maps, keep the map's values as the English source strings and pass them
  through `t()` at the point of rendering.
- **Async loading**: `i18next-http-backend` loads namespace JSON over HTTP, so wrap the app
  root in `<Suspense>` (see `frontend/src/main.tsx`) rather than assuming translations are
  available synchronously on first render.
- This is what the `Languages` item under the profile menu's `Appearance` section (see
  [home.md](../requirements/home.md#appearance)) depends on — `English` is the only selectable
  option today, but components must already be written translation-ready so a second language
  is just translation files, not a rewrite.

## File Organization

- **Pages/routes**: `frontend/src/pages/`
- **Components**: `frontend/src/components/` — feature-specific components that aren't
  shadcn/ui primitives get their own subfolder (e.g. `components/companies/`), rather than
  sitting loose alongside app-wide ones like `NavBar.tsx`
- **shadcn/ui primitives**: `frontend/src/components/ui/`
- **Hooks**: `frontend/src/hooks/`
- **API client**: `frontend/src/api/` — one place that knows about auth headers/cookies and
  base URL; components never call `fetch` directly
- **Types**: `frontend/src/types/`
- **Config**: `frontend/src/config/` — static app-wide configuration (e.g. nav items and the
  role gating they require), shared between the nav bar and route guards so the
  role → screen matrix isn't duplicated
- **Translations**: `frontend/public/locales/<lang>/<namespace>.json` — see
  [Internationalization (i18n)](#internationalization-i18n) above

## Authenticated Fetch Pattern

```ts
// frontend/src/api/client.ts owns base URL + credentials — components never fetch directly
import { apiClient } from "@/api/client";

const { data } = await apiClient.get<User>("/users/me");
```

## Testing

- **Unit/component**: Vitest
- **E2E**: Playwright — cover the auth flow (login/logout/session expiry) and primary mobile
  and desktop viewports
- Mock network calls at the API-client boundary for unit tests; use real requests against a
  running stack for E2E

## Development Commands

Run from `frontend/`.

```bash
# Install dependencies
pnpm install

# Start dev server (AI agents should never run this directly unless asked)
pnpm dev

# Build for production
pnpm build

# Lint / format
pnpm lint
pnpm format

# Unit tests
pnpm test

# E2E tests
pnpm exec playwright test
```

## Configuration

- Build-time config via Vite env vars (`VITE_*`)
