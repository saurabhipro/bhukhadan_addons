# Implementation Plan: Dashboard Area Filter

**Branch**: `001-dashboard-area-filter` | **Date**: 2026-07-21 | **Spec**: [spec.md](./spec.md)  
**Input**: User description: add Area dropdown; after Area is selected, Village options appear/filter.

## Summary

Add an **Area** cascade filter to the unified dashboard header between **Project** and **Village**. Persist selection like existing filters. Link Villages to Area Master via `area_id` so Area→Village filtering is data-backed. Extend `bhuarjan.dashboard` RPCs and OWL (`unified_dashboard.js` + `dashboard_header.xml`) used by Admin/SDM/Collector/District/Department dashboards.

## Technical Context

**Language/Version**: Python 3 (Odoo 18), OWL/JS ES modules  
**Primary Dependencies**: Odoo 18 `bhukhadan_core`, existing `bhukhadan.area.master`, `bhu.village`, `bhu.project`, `bhuarjan.dashboard`, `unified_dashboard.js`  
**Storage**: PostgreSQL via Odoo ORM (`area_id` on `bhu.village`)  
**Testing**: Manual smoke on Admin/SDM dashboards after `-u bhukhadan_core`; optional RPC checks via Odoo shell  
**Target Platform**: Odoo 18 web client (Spiffy theme compatible native selects)  
**Project Type**: Brownfield Odoo addon  
**Performance Goals**: Area/Village RPCs return project-scoped lists; avoid N+1 where practical (batch survey counts if already pattern)  
**Constraints**: Constitution — scope discipline; Coal/LARR only; upgrade-safe XML; reuse dashboard patterns; no NH/Railway/CGLRC  
**Scale/Scope**: Header filters + village form/list field + 2–3 RPCs; no payment/award redesign

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Spec/plan scope is explicit (packages/files); no drive-by refactors
- [x] Odoo touch list covers models ↔ views ↔ ACL ↔ menus/actions as needed  
      *(ACL: Area Master already has access; Village field needs no new model ACL)*
- [x] Domain stays Coal CBA / LARR; no restored NH/Railway/CGLRC without ratified spec
- [x] Security/groups and sudo usage justified *(reuse existing dashboard/group patterns; no new sudo)*
- [x] Module upgrade / asset refresh called out when XML, models, or static assets change
- [x] Complexity Tracking filled if any constitution principle is bent — N/A

## Project Structure

### Documentation (this feature)

```text
specs/001-dashboard-area-filter/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── dashboard-area-filter-rpc.md
└── tasks.md              # created by /speckit-tasks
```

### Source Code (repository root)

```text
bhukhadan_core/
├── models/masters/bhu_village.py          # add area_id
├── models/masters/area_master.py          # optional inverse village_ids
├── views/ (village views)                 # show area_id
├── dashboard/dashboard_stats.py           # get_areas_by_project, get_villages_by_project(area_id=)
├── static/src/dashboard/js/unified_dashboard.js
├── static/src/dashboard/xml/dashboard_header.xml
└── __manifest__.py                        # version bump for assets if needed
```

**Structure Decision**: Extend existing unified dashboard filter cascade and village master; no new addon.

## Complexity Tracking

> No constitution violations. Using master `area_id` on Village instead of deriving only from Survey keeps filter stable for villages without surveys.

## Phase 0 & Phase 1

See [research.md](./research.md), [data-model.md](./data-model.md), [contracts/dashboard-area-filter-rpc.md](./contracts/dashboard-area-filter-rpc.md), [quickstart.md](./quickstart.md).
