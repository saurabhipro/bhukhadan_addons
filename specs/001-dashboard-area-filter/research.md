# Research: Dashboard Area Filter

## Decision 1 — Area↔Village relationship

**Decision**: Add optional `area_id` Many2one on `bhu.village` → `bhukhadan.area.master`.

**Rationale**: Today Area Master has only `name`/`active`, and Area exists on Survey but not Village. Dashboard villages come from `project.village_ids`. Without a Village→Area link, “select Area then show Villages” has no durable master mapping. Survey.`area_id` alone would hide villages with no surveys.

**Alternatives considered**:
- Filter villages by surveys with `area_id` under project — works only for surveyed villages; fragile.
- M2M Area↔Village — overkill for current UX (one Area per Village matches Survey’s single Area).

## Decision 2 — Filter cascade UX

**Decision**: Order = Department (existing) → Project → **Area** → Village. Village disabled until Area selected.

**Rationale**: Matches user request (“after I select the Area the Village should come”) and the screenshot’s Project then Village slots.

**Alternatives considered**:
- Keep Village enabled with full project list + optional Area refine — weaker match to request.
- Area before Project — Area is not currently project-owned; Project still scopes villages.

## Decision 3 — Backend RPCs

**Decision**:
- `get_areas_by_project(project_id)` → areas used by project’s villages (`area_id` set).
- Extend `get_villages_by_project(project_id, area_id=None)` to require/filter by `area_id` when provided (dashboard will always pass Area once selected).

**Rationale**: Mirrors existing `get_villages_by_project` pattern used by `unified_dashboard.js`.

**Alternatives considered**: New dedicated controller — unnecessary; dashboard already uses `bhuarjan.dashboard` ORM calls.

## Decision 4 — Stats / domains

**Decision**: Phase 1 MVP does **not** add `area_id` to `get_dashboard_stats` domain. Area only gates Village selection; stats continue to use Project + Village (and Department) as today.

**Rationale**: User asked for dropdown cascade, not Area-level KPI aggregation. Can be a follow-up.

**Alternatives considered**: Pass `area_id` into stats and filter surveys by area — larger change, defer.

## Decision 5 — UI surface

**Decision**: Implement in shared `dashboard_header.xml` + `unified_dashboard.js` with `showAreaFilter` (default true wherever `showVillageFilter` is true).

**Rationale**: One place updates Admin/SDM/Collector/District/Department templates that already call the shared header.
