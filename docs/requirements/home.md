# Home — User Stories

The landing screen shown immediately after login, before the user navigates to a specific
screen. Inferred/drafted — there's no explicit requirement for it in [index.md](index.md) yet;
review and adjust before treating as final. See [user.md](user.md) for the Role → Screen
Access matrix this depends on.

## Navigation

A persistent navigation bar is available at all times once logged in (not specific to the home
screen — it's the app-wide navigation shell).

- **Placement**: vertical, pinned to the left edge of the screen on desktop. On mobile, it
  moves to a horizontal bar pinned to the bottom of the screen (mobile-first — see
  [frontend.md](../architecture/frontend.md)).
- **Icon-only**: no text labels in the default state, to keep the bar's footprint minimal
  (narrow on desktop, short on mobile).
- **Home is first**: a `home` icon is always the first (topmost on desktop, leftmost on mobile)
  item in the nav bar, for every authenticated user regardless of role — unlike the icons
  below it, it's not role-gated. It links to this landing screen, which is currently just an
  empty placeholder (see Open Questions).
- **Role-gated contents**: after `home`, a user only sees nav icons for the screens their
  role(s) grant. This is not duplicated here — see
  [user.md](user.md#role--screen-access) for the authoritative role → screen mapping
  (`timesheet`, `projects`, `configuration`).
- **Timesheet**: behavior depends on role — a plain navigation link for most users, but opens its
  own dropdown menu for a `project_manager`. See [Timesheet Menu](#timesheet-menu). role-gated.
- **Configuration**: Opens its own DrownDrop menu, see [Configuration Menu](#configuration-menu).
  role-gated.
- **Profile icon**: pinned at the bottom of the nav bar, separate from the role-gated screen
  icons above. Opens the profile Dropdown menu — see [Profile Menu](#profile-menu) below. Not
  role-gated; the same menu for every user.
- **Icons**: from `lucide-react` (see [frontend.md](../architecture/frontend.md#core-dependencies)):

  | Nav item        | Icon                |
  | --------------- | -------------------- |
  | `home`          | `house`               |
  | `timesheet`     | `calendar-clock`      |
  | `projects`      | `notebook-tabs`       |
  | `configuration` | `settings`            |
  | profile         | `circle-user-round`   |

- **Active state**: the icon for the currently active screen is visually highlighted, so the
  user always knows where they are given there are no text labels.
- **Consistent interaction states**: every nav bar icon button — `home`, each role-gated
  screen icon, and the profile icon — must share the exact same resting, hover, and
  active/highlighted styling. None of them gets bespoke or missing hover feedback; the profile
  icon's implementation is the reference all the others must match (see
  [frontend.md](../architecture/frontend.md#component-patterns)).
- **Tooltips**: each icon shows a tooltip on hover (the icon's label — `Home`, `Timesheet`,
  `Projects`, `Configuration`, profile/`Sign Out`), for discoverability given the bar is
  icon-only.

### Timesheet Menu

The `timesheet` nav icon's click behavior depends on role, since a `project_manager` has two
distinct destinations under it while everyone else only has one:

- **Anyone who doesn't hold `project_manager`** — a `consultant`, an `administrator`, a
  `project_admin`, or any combination of those without `project_manager`: clicking the icon
  navigates directly to the timesheet screen (their own timesheet) — same single-destination
  behavior as `home`, no dropdown. Note this means `project_admin` alone (the role that grants
  the `projects` screen — see [user.md](user.md#role--screen-access)) does **not** get this
  dropdown; `Validation` access is entirely a `project_manager` matter, independent of
  `project_admin`.
- **`project_manager`** (the literal role — not inferred from `administrator` or
  `project_admin`): clicking the icon opens a Dropdown menu with two items:
  - **My timesheet** — navigates to the same own-timesheet screen as the single-destination case
    above.
  - **Validation** — navigates to a separate screen for reviewing/validating consultants'
    submitted timesheets, restricted to the specific projects that user is assigned to as a
    project manager (see [project.md § Project Managers](project.md#project-managers) for that
    assignment mechanism). See [timesheet.md § Validation](timesheet.md#validation) for the
    screen itself (a few open questions remain — see
    [timesheet.md § Open Questions](timesheet.md#open-questions)).

This mirrors the [Configuration Menu](#configuration-menu)'s pattern (icon → dropdown → distinct
sub-screens) rather than introducing a new nav interaction shape.

### Configuration Menu

Provided the user has sufficient privilege to get this menu, clicking on the configuration icon
opens a Dropdown menu:

- **Companies** leads to `companies` configuration screen,  see [company.md](company.md)
- **Users** leads to `users` configuration screen, see see [user.md](user.md)

Future Master Data management will be provisioned here.

### Profile Menu

Clicking the profile icon opens a menu:

- **DropdownMenuGroup**, headed by a non-interactive **DropdownMenuLabel** reading
  `Appearance` (see [Appearance](#appearance) below for the full spec) — the label is not
  itself a menu item/trigger, just a heading over the two rows below it:
  - **Dark Mode** → submenu: `Light` / `Dark` / `System` (default)
  - **Languages** → submenu: `English` (only option for now)
- **DropdownMenuSeparator** 
- **Sign Out**

Unlike the icon-only top-level nav bar, these menu rows show both an icon and a text label
(there's room for it in a dropdown, unlike the icon-only bar):

| Row (submenu trigger) | Icon (`lucide-react`) |
| ---------------------- | ----------------------- |
| `Dark Mode`              | `sun-moon`                |
| `Languages`            | `languages`                |
| `Sign Out`              | `log-out`                |

The individual selectable options (`Light`/`Dark`/`System`/`English`) don't get their own
icons — the radio-style selection indicator already marks the current choice.

## Appearance

- **Theme values**: `Light`, `Dark`, or `System`. Default is `System`.
- **`System` behavior**: the app detects the user's OS/browser color-scheme preference
  (`prefers-color-scheme`) to decide whether to render the light theme  or a dark theme, 
  and updates live if that OS setting changes while the app is open.
- **Persistence**: the selected value is persisted server-side on the user record (see
  [user.md](user.md)) — it follows the user across devices and browser sessions, it's not a
  browser-local-only setting.
- **Before login**: the profile menu (and therefore the theme override) only exists once
  logged in. Pre-auth screens (e.g. the login screen) always follow `System`, since there's no
  authenticated user yet to read a persisted preference from.
- **Languages**: a single selectable option for now, `English`. Internationalisation is supported
  as a non-functional requirement through i18n, see [frontend.md](../architecture/frontend.md)

## User Stories

- As a user, I want a persistent navigation bar always available after login, so that I can
  move between screens without hunting for navigation.
- As a user, I want a `home` icon as the first item in the nav bar, always present regardless
  of my role(s), so that I can get back to a known landing point from anywhere in the app.
- As a user, I want the navigation bar to only show icons for screens I'm permitted to see, so
  that I'm not shown entry points to areas I can't access (see
  [user.md](user.md#role--screen-access)).
- As a user on mobile, I want the navigation bar at the bottom of the screen rather than the
  side, so that it's reachable with one hand and doesn't eat into limited horizontal space.
- As a user, I want a profile icon always available at the bottom of the nav bar, so that I can
  log out from anywhere in the app.
- As a consultant, whose only other accessible screen is `timesheet`, I want a minimal nav bar
  showing just `home` and `timesheet`, so that I'm not shown icons for screens I can't use.
- As a project_admin or administrator, I want the home screen to show quick links to the screens
  I can access (`projects`, `configuration`, `timesheet` as applicable), so that I can quickly
  get to what I need.
- As a project_manager, I want the `timesheet` icon to open a menu with "My timesheet" and
  "Validation", so that I can quickly switch between filling in my own timesheet and
  reviewing/validating consultants' submitted ones, without them being conflated into a single
  screen.
- As a user, I want to choose `Light`, `Dark`, or `System` from my profile menu, so that I can
  control how the app looks.
- As a user, I want `System` to be the default, so that the app matches my OS theme
  automatically without me having to configure anything.
- As a user, I want my theme choice to follow me across devices and sessions, so that I don't
  have to reconfigure it every time I log in somewhere new.
- As a user, I want a `Languages` option under `Appearance` (with only `English` selectable
  for now), so that the app is visibly ready for future localization.

## Open Questions

- **Resolved**: `home` is a distinct, always-present nav destination (the first icon, for
  every role, including `consultant`) rather than a redirect to a role's primary screen —
  there's no per-role auto-navigate away from it. For now it ships as an empty placeholder
  (see [frontend/src/pages/HomePage.tsx](../../frontend/src/pages/HomePage.tsx));
  it's planned to later host generic information and/or widgets and/or a dashboard. Exact
  content (which widgets, what "generic information" means, whether it's the same for every
  role or personalized) is not yet specified — a later-stage concern, not a blocker for
  shipping the placeholder + navigation now.
- **Resolved**: `Languages` is not persisted server-side for now — only `theme_preference` is
  (see [user.md](user.md), [database.md](../architecture/database.md)). Revisit once a second
  language actually exists.
- **Resolved**: the `Appearance`/`Dark Mode`/`Languages` profile-menu rows do get icons (see
  the table in [Profile Menu](#profile-menu) above) — unlike the icon-only top-level nav bar,
  a dropdown has room for icon + text label together.
- Should the app avoid a flash-of-wrong-theme on load (e.g. a blocking inline script applying
  the persisted/system theme before first paint), or is a brief flash acceptable for v1? Not
  yet implemented — the current implementation accepts the brief flash.
- **Resolved**: the Timesheet Menu's role split is the literal `project_manager` role,
  independent of `administrator`/`project_admin` — holding either of those without
  `project_manager` gets the direct-navigation behavior (own timesheet only), same as a
  `consultant`, with no Validation entry point. See [Timesheet Menu](#timesheet-menu). (Prior to
  the `project_manager`/`project_admin` split, this was gated by the single `manager` role — see
  [user.md § Entity](user.md#entity).)
- The **Validation** screen itself (layout, what a `project_manager` sees/does there) is not yet
  specified — see [timesheet.md § Open Questions](timesheet.md#open-questions).
