# Ifrit — Functional Requirements

## 1. Overview

Ifrit is a Project & Resource Management Web App with the following core functionalities:

- Create `projects`, `companies` and `users`
- Manage `projects`, `companies` and `users`
- A `Company` is always usable as a project `client`; it can additionally be flagged
  `is_vendor` to also be usable as a project `vendor` (see [company.md](company.md))
- A project must have a `vendor` entity and a `client` entity — the same company may be both
  on the same project (inter-company/self-billing)
- A project must have an `invoicing currency`
- A project must have a `project type`: time and material, fixed price, capped T&M
- A project can have 0..N `Service Lines`
- Each `service line` can have 0..N associated `Users`
- Each `service line` must have a `quantity` and `unit price`
- `users` roles are `administrator`, `manager` or `consultant`
- A `user` can have multiple roles attached
- A `consultant` can only see one screen: `timesheet`
- A `manager` can additonally see `projects`
- An `administrator` can see screens to edit `companies` and `users`


## 2. User Stories


- [auth.md](auth.md) — User stories related to authentication
- [user.md](user.md) — Defines what is the user
- [project.md](project.md) — component structure, state management, styling rules
- [company.md](company.md) — schema conventions, migrations, indexing rules
- [home.md](home.md) — User stories for the post-login home/landing screen


## 3. Entities

<!-- Core data entities. Keep these in sync with the actual schema once it exists;
     schema must satisfy BCNF per AGENTS.md, so note key attributes/functional
     dependencies here where non-obvious. -->


## 6. Non-Functional Requirements

See [index.md](../architecture/index.md)

## 7. Out of Scope

<!-- Explicitly excluded features/behaviors, to prevent scope creep during implementation. -->

## 8. Open Questions

<!-- Unresolved decisions to settle before/during implementation. -->
