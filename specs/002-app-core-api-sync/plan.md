# Implementation Plan: Mobile App ↔ Core Sync

**Branch**: `002-app-core-api-sync` | **Date**: 2026-07-21 | **Spec**: [spec.md](./spec.md)  
**Input**: User description: link `bhukhadan_app` with `bhukhadan_core` mobile APIs, keep survey fields aligned, add Area dropdown, and show Villages only after Area selection.

## Summary

Align the **Flutter** app (`bhukhadan_app`), `bhukhadan_core` mobile APIs, and `survey.py` so login, full survey field capture, Khasra prefill, and Project → Area → Village cascade work end-to-end in one delivery. Extend API serialize/write paths for any mobile-capture fields still missing (notably `area_id` in responses, `mb_*` checklist fields), add master-data endpoints for dropdowns, and update Flutter survey screens to mirror `survey_views.xml` sections.

## Technical Context

**Language/Version**: Python 3 (Odoo 18) + **Flutter/Dart** (`bhukhadan_app`)  
**Primary Dependencies**: Odoo 18 `bhukhadan_core`, mobile auth + survey REST controllers, `utils/survey_api.py`, `models/survey/survey.py`, `views/survey_views.xml`, Flutter survey screens/models/services  
**Storage**: PostgreSQL via Odoo ORM  
**Testing**: Manual API smoke tests plus mobile UAT; optional Odoo shell / curl verification for auth and survey endpoints  
**Target Platform**: Odoo 18 backend APIs serving the BhuKhadan mobile app  
**Project Type**: Brownfield Odoo addon with external mobile-client integration  
**Performance Goals**: Mobile dropdown/master-data endpoints should return project-scoped data quickly enough for normal form interaction; Khasra-prefill lookups should feel immediate in field use  
**Constraints**: Coal CBA / LARR only; authenticate all mobile endpoints; keep same-delivery backend + mobile parity; avoid drive-by refactors; call out `-u bhukhadan_core` if controllers/models/views/static change  
**Scale/Scope**: Flutter survey UI parity with `survey.py`, API gap closure, master-data dropdowns, Khasra prefill, Area cascade; award/objection desk sections remain backend-only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Spec/plan scope is explicit (packages/files); no drive-by refactors
- [x] Odoo touch list covers models ↔ views ↔ ACL ↔ menus/actions as needed  
      *(Likely controllers + helpers + survey model/domain logic; no new business model expected, ACL impact should stay within existing survey access patterns.)*
- [x] Domain stays Coal CBA / LARR; no restored NH/Railway/CGLRC without ratified spec
- [x] Security/groups and sudo usage justified  
      *(Mobile endpoints already use JWT/OTP plus survey access checks; plan keeps that pattern and tightens contract parity rather than widening access.)*
- [x] Module upgrade / asset refresh called out when XML, models, or static assets change
- [x] Complexity Tracking filled if any constitution principle is bent — N/A

## Project Structure

### Documentation (this feature)

```text
specs/002-app-core-api-sync/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── mobile-app-core-api.md
│   └── survey-field-parity.md   # survey.py ↔ API ↔ Flutter matrix
└── tasks.md              # created by /speckit-tasks
```

### Source Code (repository root)

```text
bhukhadan_core/
├── controllers/api/auth.py            # OTP request/login session contract
├── controllers/api/main.py            # Bearer-token permission gate
├── controllers/api/survey_api.py      # survey CRUD / detail / list / append endpoints
├── utils/survey_api.py                # writable fields, validation, serialization, Khasra query handling
├── models/survey/survey.py            # survey Area/Village relationship behavior
├── models/masters/bhu_village.py      # village ↔ Area master link already in place
├── models/masters/area_master.py      # Area master used by mobile dropdowns
├── dashboard/dashboard_stats.py       # reusable project→Area→Village lookup methods
├── views/survey_views.xml             # canonical UI section/field layout for Flutter parity
└── __manifest__.py                    # version bump if controllers/helpers change

bhukhadan_app/                         # Flutter app (separate repo/path; same delivery)
├── lib/                               # survey screens, models, API client, state
├── models/ or entities/               # Dart models mirroring survey payload
└── services/                          # auth + survey + master-data API calls
```

**Structure Decision**: `survey_views.xml` + `survey.py` define what Flutter must capture; `utils/survey_api.py` is extended to close parity gaps; Flutter `bhukhadan_app` is updated in the same release — not API-only.

## Complexity Tracking

> No constitution violations. Coordination complexity: Flutter app may live outside this repo — `survey-field-parity.md` and explicit Flutter screen tasks keep backend and app in sync.

## Phase 0 & Phase 1

See [research.md](./research.md), [data-model.md](./data-model.md), [contracts/mobile-app-core-api.md](./contracts/mobile-app-core-api.md), [contracts/survey-field-parity.md](./contracts/survey-field-parity.md), and [quickstart.md](./quickstart.md).
