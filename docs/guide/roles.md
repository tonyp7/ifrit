# Roles

Every user has one or more of four roles. What a user sees and can do is the union of their roles.
Roles are matched literally: being an `administrator` does not make someone a `manager`, and the
other way round.

| Role | Purpose | Screens it adds |
|---|---|---|
| **Consultant** | Logs hours on service lines they are assigned to. | Timesheet (every user has it) |
| **Manager** | Creates and maintains projects, their service lines, assignments and documents, and reviews, corrects, locks and exports hours. On every project: being listed as a project's manager only decides what "Only see my projects" shows. | Reporting, Projects |
| **Billing** | Prepares invoices from projects' logged hours. Billing alone gives no access to the Projects or Configuration screens. | Invoices |
| **Administrator** | Manages users, companies and application-wide settings. | Configuration |

## Navigation

After signing in, a narrow bar on the left (at the bottom on a phone) shows only the screens your
roles give you, each as an icon with a tooltip:

| Roles | Bar |
|---|---|
| Consultant | Timesheet, profile |
| Manager | Timesheet, Reporting, Projects, profile |
| Billing | Timesheet, Invoices, profile |
| Administrator | Timesheet, Configuration, profile |
| Several roles | Everything each of them grants |

Typing the address of a screen you do not have takes you back to your own timesheet.

The **profile** icon opens a menu where you choose the appearance (light, dark or follow the
system) and sign out. Your theme choice is stored with your account, so it follows you between
devices.

## Things that apply to everyone

- **Accounts are created by an administrator.** There is no self-registration. If you forget your
  password, ask an administrator to set a new one.
- **Deactivated, not deleted.** Users, companies, projects and service lines that are removed
  are deactivated, not erased, so past hours and reports stay intact.
- **Hours** are entered in half-hour steps, from 0 to 24 per service line per day.

## Upgrading from separate project roles

Earlier versions had two roles, **project admin** (Projects) and **project manager** (Reporting,
limited to the projects they were assigned to). Upgrading merges them into **manager** for
everyone who held either one. Someone who held only one of them therefore gains the other's
screens, and every manager can now act on every project. Before upgrading, an administrator should
review the users who held only one of the two roles.

## Which guide to read

- [Timesheet](timesheet.md): logging hours, for everyone with the consultant role.
- [Reporting](reporting.md): review, correction, locking and export, for managers.
- [Projects](projects.md): projects, service lines, assignments and documents, for managers.
- [Invoices](invoices.md): preparing invoices, for the billing role.
- [Administration](administration.md): users, companies and settings, for administrators.
