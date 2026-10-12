# Administration

Administrators manage the people, companies and global settings that everything else builds on.
Everything is under the **Configuration** icon in the navigation bar, which has three tabs:
**General**, **Companies** and **Users**.

Removing a user or a company *deactivates* it: it disappears from lists and can no longer be used,
but everything recorded against it is kept. Deactivation cannot be undone from the application.

## General

### Organization logo

Upload a JPEG, PNG or WebP image with **Browse**. Only one logo exists: uploading a new one replaces
the current one, and a failed upload leaves the current one unchanged. The logo can also be removed.

### PDF report export

The **PDF Report Export** card controls the logo in exported PDF reports:

- a switch, **Insert organization logo in exported PDF** (on by default),
- a slider, **Logo height, in mm**, from 1 to 60 (20 by default).

The slider keeps its value while the switch is off.

## Companies

Companies are the vendors and clients that projects refer to. Both administrators and project
admins can see the list (project admins need it to pick a project's vendor and client), but only
administrators can create or change companies.

### Fields

| Field | Notes |
|---|---|
| **Legal name** | Required. |
| **Trading name** | Optional. |
| **Legal form** | Optional. |
| **Country** | Two-letter country of registration. |
| **Vendor** | Off by default. Only a company flagged as a vendor can be a project's vendor. Any active company can be a client. |

A company can also hold several **identifiers** (such as a tax or registration number) and
**addresses**. Add, edit, duplicate and delete them from the company's form. These are removed
for good rather than deactivated.

### Actions

- **New**, **Edit** and **Duplicate** use the same form. Duplicate starts a new company from an
  existing one.
- **Delete** asks for confirmation and deactivates the company. Projects that already refer to it
  stay readable.

## Users

### Create a user

Choose **New**, then fill in:

- the full name,
- the login identity, which is the user's email address,
- one or more roles (`consultant` is preselected), see [Roles](roles.md),
- an initial password.

Login identities must be unique among active users. A person cannot sign up on their own; every
account starts here.

### Passwords

A password must be 12 to 255 characters and may contain letters, digits, spaces and symbols but no
control characters. A strength indicator under the field updates as you type.

To help someone who forgot their password, open their record in the users list and set a new one.
Doing so ends all of that user's current sessions.

### Edit, duplicate, deactivate

- **Edit** changes name, login identity and roles.
- **Duplicate** pre-fills a new user from an existing one, for example to create a colleague with
  the same roles.
- **Delete** asks for confirmation and deactivates the account. The user can no longer sign in
  and loses any open session, is removed as project manager from every project, and keeps their
  logged history. Their login email can be used again for a new account.

You cannot deactivate your own account or remove your own `administrator` role, even if other
administrators exist.

### A leaver on a project

A deactivated consultant stays on the service lines they were assigned to, so a project manager can
still review and lock their final timesheet in [Reporting](reporting.md).
