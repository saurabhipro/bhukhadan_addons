# BhuKhadan Constitution

Governing principles for AI-assisted and human development of the BhuKhadan
Odoo 18 addons (`bhukhadan_core`, `bhukhadan_web`, `workflow_demo`).

## Core Principles

### I. Spec Before Code (medium+ work)
Non-trivial features, cross-cutting cleanups, API changes, and dashboard work
MUST go through Spec Kit: specify → (clarify) → plan → tasks → (analyze) →
implement. Tiny one-line fixes may skip the full loop. Specs define **what**
and **why**; plans define **how** within this constitution.

### II. Odoo Module Integrity (NON-NEGOTIABLE)
- Keep Odoo 18 conventions: models, views XML, security CSV/XML, menus,
  reports, and `__manifest__.py` data order stay consistent.
- New models require ACL rows; new menus need actions; client actions need
  registered OWL tags.
- Prefer upgrade-safe XML (`noupdate` only when intentional). After model/view
  changes, call out `-u bhukhadan_core` (or the touched module).
- Do not invent module technical names; primary module is `bhukhadan_core`.
  Legacy `bhuarjan.*` action tags may be aliased for compatibility, but new
  work uses `bhukhadan_core.*`.

### III. Scope Discipline
Change only what the active spec/task requires. No drive-by refactors, no
unrelated formatting, no opportunistic dependency bumps. If a cleanup is
needed, add it as an explicit task in the plan.

### IV. Domain Focus: Coal CBA + LARR
BhuKhadan digitizes land acquisition under the **Coal Bearing Areas Act** and
**RFCTLARR**. Keep section flows, dashboards, awards, surveys, and payments
aligned with that domain. Do not reintroduce removed acts (National Highway
3A/3C/3D, Railways 20A/20D/20E, CGLRC 247) unless a ratified spec explicitly
restores them.

### V. Security & Access First
Every user-facing model/action must respect groups (`group_bhuarjan_*`,
system). Never weaken ACLs or sudo without justification in the plan.
Controllers/API must authenticate and authorize; do not expose internal
models publicly. Secrets, OTP dumps, and credentials never belong in git.

### VI. UI Consistency
Backend OWL dashboards (admin/SDM/collector/district/department), Spiffy
theme constraints, and website (`bhukhadan_web`) should follow existing
patterns. Prefer shared dashboard helpers over one-off copies. Hindi/English
labels already in use should stay consistent when touching the same screens.

### VII. Simplicity & Traceability
Prefer the smallest change that meets the spec. Prefer extending existing
section/dashboard patterns over new frameworks. Commit messages and PR
summaries explain **why**. Specs and plans stay in the repo as the source of
intent for brownfield work.

## Stack & Repo Constraints

- **Runtime**: Odoo 18, Python models, XML data/views, OWL/JS assets.
- **Addons path**: this repo is mounted under Odoo `addons_path`; do not assume
  the old `bhuarjan` package path is active.
- **Packages**: `bhukhadan_core` (business), `bhukhadan_web` (website),
  `workflow_demo` (BPMN demo) — touch only packages named in the plan.
- **Seed data**: many `data/*.xml` files are commented out in the manifest
  because live DBs are already populated; do not blindly re-enable them.
- **Assets**: bump module version or document asset refresh when changing
  JS/XML under `static/`.

## Development Workflow

1. Establish/update this constitution when principles change.
2. `/speckit-specify` — requirements and acceptance criteria.
3. `/speckit-clarify` — resolve ambiguities (recommended for production).
4. `/speckit-plan` — Odoo touch list: models, views, security, menus,
   dashboards, APIs, migrations.
5. `/speckit-tasks` — ordered, testable units.
6. `/speckit-analyze` — optional consistency gate.
7. `/speckit-implement` — execute tasks only.
8. Human review + module upgrade + smoke test (login, role dashboard, key
   section form, critical API if touched).

## Governance

- This constitution supersedes ad-hoc agent habits when they conflict.
- Amendments require updating this file, bumping the version below, and noting
  the reason in the PR/commit.
- PRs that change process expectations should update dependent Spec Kit
  templates only when headings or required plan/spec sections change.
- Complexity or exceptions must be justified in the feature plan.

**Version**: 1.0.0 | **Ratified**: 2026-07-21 | **Last Amended**: 2026-07-21
