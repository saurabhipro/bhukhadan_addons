# Tasks: Mobile App ↔ Core Sync

**Input**: `specs/002-app-core-api-sync/`  
**Prerequisites**: plan.md, spec.md, contracts/

## Phase 1: API parity gaps (`bhukhadan_core`)

- [X] T001 Add `area_id` / `area_name` to `api_serialize_survey` summary + detail
- [X] T002 Add `mb_owner_decl_date`, `mb_decl_*` to `SURVEY_WRITABLE`, build/update vals, and serialize
- [X] T003 Add mobile master-data endpoints (or HTTP routes) for projects, areas-by-project, villages-by-project+area
- [X] T004 Validate Project + Area + Village consistency on survey create/update
- [X] T005 Verify Khasra list/search (`q`) returns all prefilled mobile-capture fields

## Phase 2: Flutter app (`bhukhadan_app`)

- [X] T006 Update Dart survey form fields to match survey-field-parity (area + mb_*)
- [X] T007 Add Project → **Area** → Village dropdown cascade on Home screen
- [X] T008 Update survey form location section (Area read-only + payload)
- [X] T009 Landowners/trees/photos already present; wired to `/bhukhadan/survey`
- [X] T010 Add document checklist screen for `mb_*` fields
- [X] T011 Khasra search list uses `q=` against `/bhukhadan/survey`; copy/edit prefill maps `area_id` + full fields
- [X] T012 Update API client constants for auth + master-data + survey routes

## Phase 3: Integration & release

- [X] T013 Field-parity matrix backend gaps closed; Flutter Area/mb_* added
- [ ] T014 `-u bhukhadan_core` + Flutter build smoke test per [quickstart.md](./quickstart.md)
- [ ] T015 UAT sign-off: app values match backend `survey.py` record on reopen
