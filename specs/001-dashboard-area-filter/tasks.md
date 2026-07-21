# Tasks: Dashboard Area Filter

**Input**: `specs/001-dashboard-area-filter/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup

- [X] T001 Verify feature docs and note upgrade `-u bhukhadan_core` after changes
- [X] T002 [P] Confirm ignore files already cover Python/`graphify-out` (no change unless missing)

## Phase 2: Foundational

- [X] T003 Add `area_id` on `bhu.village` in `bhukhadan_core/models/masters/bhu_village.py`
- [X] T004 [P] Optional inverse `village_ids` on `bhukhadan.area.master` in `area_master.py`
- [X] T005 Expose `area_id` on village form/list/search views
- [X] T006 Add `get_areas_by_project` and extend `get_villages_by_project` in `dashboard_stats.py`

## Phase 3: User Story 1 — Area then Village cascade (P1) 🎯 MVP

- [X] T007 [US1] Add Area `<select>` between Project and Village in `dashboard_header.xml`
- [X] T008 [US1] State/config/`showAreaFilter`, loadAreas, onAreaChange, gate Village in `unified_dashboard.js`
- [X] T009 [US1] Wire Project change to clear Area+Village and reload Areas

## Phase 4: User Story 2 — Persist Area (P2)

- [X] T010 [US2] localStorage restore/save for Area (+ name) with village validity checks

## Phase 5: User Story 3 — Master data usable (P3)

- [X] T011 [US3] Ensure village views editable for Area; Area Master remains available under Master Data

## Phase 6: Polish

- [X] T012 Bump `bhukhadan_core` version for asset refresh if needed
- [X] T013 Mark tasks complete; note manual quickstart validation
