# Tasks: Screenshot Tracker

**Input**: Design documents from `/specs/003-screenshot-tracker/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not requested in spec — no TDD task phase; validation via quickstart.md in Polish.

**Organization**: Tasks grouped by user story for independent delivery.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: `[US1]` / `[US2]` / `[US3]` for story phases only
- Include exact file paths

## Path Conventions

- Odoo: `bhukhadan_core/`
- Flutter: `bhukhadan_app/lib/...`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align feature branch/docs and confirm touch targets

- [X] T001 Confirm active feature dir `specs/003-screenshot-tracker` in `.specify/feature.json` and review plan touch list
- [X] T002 [P] Verify `bhukhadan_app` and `bhukhadan_core` paths exist and are writable for this delivery

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Persist screenshot audit entity + ACL so admin UI and mobile API can land

**⚠️ CRITICAL**: No user story work until this phase completes

- [X] T003 Create model `bhu.screenshot.log` in `bhukhadan_core/models/screenshot_log.py` per `data-model.md`
- [X] T004 Register import in `bhukhadan_core/models/__init__.py`
- [X] T005 [P] Add admin/system read+unlink ACL rows in `bhukhadan_core/security/ir.model.access.csv`
- [X] T006 Register `views/screenshot_log_views.xml` and bump version in `bhukhadan_core/__manifest__.py`

**Checkpoint**: Model + ACL + manifest ready

---

## Phase 3: User Story 1 - Admin reviews screenshot audit trail (Priority: P1) 🎯 MVP

**Goal**: Administrator-only Odoo list/form showing who / screen / when / IP; search/filter; delete allowed

**Independent Test**: With sample rows (shell/API or UI create via sudo in shell), admin opens **Users → Screenshot Audit Log**, filters, opens detail, deletes; District Admin cannot see menu

### Implementation for User Story 1

- [X] T007 [US1] Create list/form/search/action in `bhukhadan_core/views/screenshot_log_views.xml` (no create/edit; delete allowed)
- [X] T008 [US1] Add **Users → Screenshot Audit Log** menu (admin+system only) in `bhukhadan_core/views/menuitem.xml`
- [X] T009 [US1] Harden menu `groups_id` to Administrator + System only (exclude District Admin) in `bhukhadan_core/views/menuitem.xml`
- [X] T010 [US1] Smoke-check field labels cover user, login/mobile/role, IP, platform, screen, survey, device, time

**Checkpoint**: Admin UI MVP usable once any log rows exist

---

## Phase 4: User Story 2 - Mobile app reports screenshot events (Priority: P1)

**Goal**: Authenticated mobile posts create audit rows with IP; offline queue+retry; brief non-blocking notice; screen/survey context

**Independent Test**: Bearer `POST /api/bhukhadan/audit/screenshot` creates admin row; Flutter detect (or debug trigger) shows notice and appears in log; offline then online flushes queue

### Implementation for User Story 2

- [X] T011 [US2] Implement `POST /api/bhukhadan/audit/screenshot` with `@check_permission`, IP capture, sudo create in `bhukhadan_core/controllers/api/survey_api.py` per `contracts/screenshot-audit-api.md`
- [X] T012 [P] [US2] Add `screenshotAudit` endpoint constant in `bhukhadan_app/lib/src/constants/api_constants.dart`
- [X] T013 [P] [US2] Add queue storage keys/helpers in `bhukhadan_app/lib/src/utils/storage.dart`
- [X] T014 [US2] Create `bhukhadan_app/lib/src/services/screenshot_audit_service.dart` (detect hook, enqueue, flush/retry, current screen/survey context)
- [X] T015 [US2] Wire service start + notice (SnackBar/toast) from `bhukhadan_app/lib/src/app.dart` and/or `bhukhadan_app/lib/src/navigation/app_navigation.dart`
- [X] T016 [US2] Update screen context on major routes (home/login/survey list/create/details) so `screen_name` / `survey_id` populate
- [X] T017 [US2] Ensure report failures never crash UI; flush queue after login / resume / connectivity restore

**Checkpoint**: Detectable screenshots (or debug POST from app) land in admin log with user+IP

---

## Phase 5: User Story 3 - Reduce silent leakage on hard-to-detect platforms (Priority: P2)

**Goal**: Block/obscure system screenshots on **all** app screens where OS allows (Android FLAG_SECURE; iOS best-effort)

**Independent Test**: On Android, screenshot of any foreground app screen is blank/blocked; iOS still logs when detection fires

### Implementation for User Story 3

- [X] T018 [US3] Enable window `FLAG_SECURE` (or equivalent secure-screen plugin) for whole app in `bhukhadan_app/android/app/src/main/kotlin/com/example/bhuarjan/MainActivity.kt` and/or Flutter bootstrap
- [X] T019 [P] [US3] Confirm iOS Info/AppDelegate path does not disable detection; document any iOS blocking limits in `bhukhadan_app/README.md` note if needed
- [X] T020 [US3] Verify blocking applies across login/home/survey flows (manual spot-check checklist in quickstart)

**Checkpoint**: Android blocking + existing US2 logging coexist

---

## Phase 6: User Story 4 - Odoo web identity watermark (Priority: P2)

**Goal**: Non-blocking repeating watermark on Odoo backend with signed-in name/login/uid so web screenshots remain attributable (no fake browser audit rows)

**Independent Test**: Sign into `/web`, screenshot any backend page — watermark text for that user is readable; clicks still work

### Implementation for User Story 4

- [X] T021 [US4] Add `bhukhadan_core/static/src/css/screenshot_watermark.css` (fixed overlay, low opacity, `pointer-events: none`, repeating diagonal text)
- [X] T022 [P] [US4] Add `bhukhadan_core/static/src/js/screenshot_watermark.js` mounting overlay from `@web/session` (name, login/username, uid)
- [X] T023 [US4] Register both assets under `web.assets_backend` in `bhukhadan_core/__manifest__.py`
- [X] T024 [US4] Spot-check watermark on list/form/dashboard; confirm it does not block clicks and differs per signed-in user

**Checkpoint**: Web screenshots carry identity; audit log still mobile/API only

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Upgrade path, API smoke, quickstart validation

- [X] T025 Document `-u bhukhadan_core` (+ asset refresh) and watermark check in `specs/003-screenshot-tracker/quickstart.md` if gaps remain
- [X] T026 [P] Add Playwright/API smoke case for audit POST in `bhukhadan_test/tests/` (optional if time) or curl steps already in quickstart
- [X] T027 Run admin ACL + API + mobile + watermark spot-checks from `specs/003-screenshot-tracker/quickstart.md`
- [X] T028 Mark completed tasks `[X]` and note platform / watermark limits in `specs/003-screenshot-tracker/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → no deps
- **Foundational (Phase 2)** → after Setup; **blocks** all stories that need the model
- **US1 (Phase 3)** → after Foundational (MVP admin UI)
- **US2 (Phase 4)** → after Foundational; needs model for API create; can follow US1
- **US3 (Phase 5)** → Flutter-only; can start after US2 service exists (or parallel with US2 Android work once T014 planned)
- **US4 (Phase 6)** → Odoo assets only; independent of Flutter; can run after or parallel with US1 once manifest bump is coordinated
- **Polish (Phase 7)** → after desired stories

### User Story Dependencies

- **US1**: Independent after Phase 2 (seed rows via Odoo shell if API not ready)
- **US2**: Needs Phase 2 model; delivers live data into US1 UI
- **US3**: Complements US2; does not block US1
- **US4**: Independent of mobile; no `bhu.screenshot.log` writes from browser

### Parallel Opportunities

- T002 with T001
- T005 with T003/T004 (after model file exists carefully — prefer T003→T004 then T005[P] with T006)
- T012/T013 after T011 contract known
- T019 parallel with T018
- T021/T022 parallel; then T023 register assets

---

## Parallel Example: User Story 2

```bash
# After T011 API exists:
Task: "Add screenshotAudit in bhukhadan_app/lib/src/constants/api_constants.dart"
Task: "Add queue keys in bhukhadan_app/lib/src/utils/storage.dart"
# Then sequential service + wiring:
Task: "Create screenshot_audit_service.dart"
Task: "Wire app.dart / navigation"
```

## Parallel Example: User Story 4

```bash
Task: "Create screenshot_watermark.css"
Task: "Create screenshot_watermark.js"
# Then:
Task: "Register in __manifest__.py web.assets_backend"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 + 2  
2. Phase 3 US1  
3. Seed one log via Odoo shell → validate admin menu/filter/delete  
4. Demo MVP

### Incremental Delivery

1. US1 admin UI  
2. US2 API + Flutter report/notice/queue  
3. US3 app-wide FLAG_SECURE  
4. US4 Odoo web identity watermark  
5. Quickstart validation

---

## Notes

- No automated test tasks unless added later — spec did not request TDD
- API create uses sudo after JWT; UI has no create/write
- Web watermark ≠ screenshot detection; do not invent browser audit rows
- Keep changes scoped to `bhukhadan_core` + `bhukhadan_app`
