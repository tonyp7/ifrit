# Changelog

All notable changes to Ifrit Timesheet Tracker are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[semantic versioning](https://semver.org).

## [2.0.0] - 20 Oct 2026

### Upgrading

Read this before moving from 1.x. **Back up the database and the storage volume first.**

- **The database changes, and only forward.** Two migrations run when the container starts. One of
  them cannot be undone: once an invoice has been issued, the invoicing migration refuses to go back,
  and the role migration cannot tell who held which role. To return to 1.x, restore your backup.
- **Roles are merged.** The *project admin* and *project manager* roles are now one role,
  **manager**. Everyone who held either, or both, becomes a manager. Check your users afterwards: see
  "Upgrading from separate project roles" in the
  [user guide](https://docs.ifrit.day/guide/roles/).
- **The image is bigger and uses more memory.** It now includes LibreOffice, which makes the invoice
  PDFs: about 1.07 GB instead of about 497 MB. Each PDF takes up to about 225 MB of memory while it is
  made, and two at most are made at once. A custom image must include LibreOffice too, otherwise issuing
  an invoice is refused with a "PDF engine is not available" error.
- **Set your time zone.** `TZ` is optional (UTC when unset) but decides the date on an invoice and the
  year, month and day in its number. Set it to your organization's time zone before issuing invoices.
  See [Configuration](https://docs.ifrit.day/configuration/#time-zone).

### Added

**Invoicing**
- A **billing** role and an **Invoices** screen, with a list you can search and whose columns you can
  choose.
- Invoices for Time & Material projects, with lines generated from the hours logged on service lines
  over a period, and for Fixed Price projects, with **billing milestones** on the project. Generating
  adds to the lines already on a draft.
- References on projects and invoices (purchase order, contract and others), and **payee accounts** on
  companies, copied onto the invoice. A payee account is chosen for you when the vendor has one.
- Taxes on an invoice, as a rate or as an amount, one after another or compounding.
- **Issuing** an invoice gives it a number and freezes everything on it, and **voiding** cancels it
  while keeping its number.
- Configurable **invoice numbering** (year, month, day, a counter, fixed text), the **Document Name**
  setting (for example "Tax Invoice") and the **Standard Workday Length** setting that turns hours into
  days.
- **PDF invoices.** **Preview** shows the PDF of a draft with a DRAFT mark, without saving it. The PDF
  is made when the invoice is issued and kept, and **Download PDF** gives that same file from then on.
  Voiding draws a VOIDED mark on it. An administrator can replace the layout with their own
  OpenDocument template under Configuration, check it with a sample first, and reset to the default.

**Elsewhere**
- A searchable **country picker** with flags for addresses.
- A documentation site at [docs.ifrit.day](https://docs.ifrit.day/), with a user guide, a self-hosting guide and a configuration reference.
- The `TZ` setting for the server's time zone.

### Changed
- **Breaking:** the *project admin* and *project manager* roles are merged into **manager** (see
  Upgrading).
- Locked cells in the timesheet are drawn slate-blue with a hatch instead of red.
- The container image includes LibreOffice (see Upgrading).
- Behind the scenes: the backend is type-checked with pyrefly and both the backend and the frontend
  are checked for formatting in CI, and the backend tests run in parallel.

### Fixed
- Uploading the organization logo no longer fails when another upload replaces it at the same moment.
- The service line dialog shows the consultants already assigned to the line.

## [1.1.1] - 9 Oct 2026

### Changed
- Python 3.14 is now the only supported version, in the container image and for running the
  backend locally. Docker users need to do nothing.
- The frontend now runs on current major versions of its main libraries (React Router 8,
  TypeScript 6, Node 26, zod 4 and others), and the backend dependencies are refreshed.

### Fixed
- Form validation messages, for example for an empty password in the user form, show up
  correctly again.
- Sorting a list of users, companies or projects while on a later page now returns to the first
  page with a single request, instead of fetching a stale page first.
- The theme preference follows the signed-in user when you sign in or out, and "System" tracks
  the operating system's colour scheme live.

## [1.1.0] - 8 Oct 2026

### Added
- A favicon, in SVG with `.ico` and Apple touch icon fallbacks, so the app is recognizable in
  browser tabs, bookmarks and on home screens.
- An ACKNOWLEDGMENTS file crediting the third-party software the project builds on.
- A "Reload" prompt when a page fails to load, which happens when a tab left open across an update
  asks for files that no longer exist. Navigation stays on screen and the message clears when you
  move to another page.

### Changed
- Pages you can only reach with a role (reporting, projects, companies, users and the
  configuration screens) now load on demand. The initial download is about half the size (232 kB to
  118 kB gzipped), which speeds up the login page and first load, especially on mobile.

### Fixed
- The desktop timesheet grid now fits inside shorter screens, including MacBook Air logical
  resolutions below 1080p, instead of spilling past the viewport.

## [1.0.0] - 6 Oct 2026

The first release.

### Added

**Time tracking**
- A personal timesheet in a week or month view that adapts to phones and desktops. Hours are entered
  per service line per day, cells autosave, and the server enforces which lines a user may log
  against and which periods are locked.
- Locking: a project manager can freeze and thaw a consultant's hours for a service line over a
  period, so submitted time can no longer change.

**Projects and companies**
- Projects with a vendor, client, currency, type and status, broken into service lines with
  consultants and prices, and with project managers assigned to review each project's timesheets.
- Supporting documents on a project (contracts, purchase orders, signed addenda), labelled with tags
  from a fixed vocabulary, which can be downloaded or removed later.
- Companies, as clients and vendors, with their legal identifiers and addresses in a model shaped for
  Peppol and UBL.

**Reporting and export**
- A filterable cross-consultant report over the projects a manager manages, using the same grid as
  the personal timesheet, where hours can be reviewed, corrected and locked.
- Export of the report you are looking at as PDF, Excel or CSV, always generated fresh from stored
  data, with user-entered text handled safely.
- The PDF can carry the organization's logo. An administrator chooses, in Configuration, whether the
  logo is included and how tall it is.

**Administration**
- User accounts with fine-grained roles (administrator, project admin, project manager, consultant),
  local sign-in, password reset by an administrator, and deactivation that preserves history.
- A Configuration area with the organization logo, the PDF export settings, companies and users.
- Instance-wide runtime settings that an administrator can change without a redeploy.

**Platform**
- Cookie-based sessions with silent refresh, and revocation on sign out or password reset.
- Light, dark and system themes that follow the user across devices.
- Uploaded files stored on disk, validated and served only to users allowed to see the object they
  belong to.
- A single container image (nginx, the web app and the API) with a standard PostgreSQL 18 database,
  deployed with Docker Compose. Database migrations are applied automatically on start.

### Not included in this release
- Single sign-on (SAML). Only the account flag exists; accounts sign in with email and password.
- Peppol or UBL invoice export. The company model is shaped for it, but nothing exports yet.
