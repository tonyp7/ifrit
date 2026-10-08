# Changelog

All notable changes to Ifrit Timesheet Tracker are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[semantic versioning](https://semver.org).

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
