# Roles

Every user has one or more of four roles. What a user sees and can do is the union of their roles.
Roles are matched literally: being an `administrator` does not make someone a `project_admin`, and
the other way round.

| Role | Purpose | Screens it adds |
|---|---|---|
| **Consultant** | Logs hours on service lines they are assigned to. | Timesheet (every user has it) |
| **Project manager** | Reviews, corrects, locks and exports the hours of the people on the projects they manage. | Reporting |
| **Project admin** | Creates and maintains projects, their service lines, assignments and documents. | Projects |
| **Administrator** | Manages users, companies and application-wide settings. | Configuration |

## Navigation

After signing in, a narrow bar on the left (at the bottom on a phone) shows only the screens your
roles give you, each as an icon with a tooltip:

| Roles | Bar |
|---|---|
| Consultant | Timesheet, profile |
| Project manager | Timesheet, Reporting, profile |
| Project admin | Timesheet, Projects, profile |
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

## Which guide to read

- [Timesheet](timesheet.md): logging hours, for everyone with the consultant role.
- [Reporting](reporting.md): review, correction, locking and export, for project managers.
- [Projects](projects.md): projects, service lines, assignments and documents, for project admins.
- [Administration](administration.md): users, companies and settings, for administrators.
