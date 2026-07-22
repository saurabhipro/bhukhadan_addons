# Implementation Plan: Screenshot Tracker

**Branch**: `003-screenshot-tracker` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-screenshot-tracker/spec.md`

## Summary

Deliver an administrator-only Odoo audit view of mobile screenshot events (who / what screen / when / IP) and wire the Flutter app to detect screenshots where possible, show a brief recorded notice, queue offline events for retry, block screenshots on all app screens where the OS allows, and POST authenticated events to `bhukhadan_core`. For Odoo **web** (where Print Screen cannot be detected), add a non-blocking **identity watermark** (name/login/uid) over the backend UI so leaked screenshots remain attributable.

Reuse existing JWT mobile auth (`check_permission`). Create `bhu.screenshot.log` with admin/system ACL (read + unlink), list/form/search views, Users menu entry, and `POST /api/bhukhadan/audit/screenshot`. Flutter: global screenshot listener + secure window flags + local queue via SharedPreferences (or equivalent) + SnackBar/toast notice. Web: lightweight `web.assets_backend` JS/CSS overlay using `session` identity.

## Technical Context

**Language/Version**: Python 3 (Odoo 18) + Flutter/Dart 3 (`bhukhadan_app`)  
**Primary Dependencies**: `bhukhadan_core` models/views/security/controllers; Flutter `ApiService`, SharedPreferences, platform channels / FlutterSecureScreen or `FLAG_SECURE` / iOS screenshot notification  
**Storage**: PostgreSQL via Odoo ORM; on-device queue for offline events  
**Testing**: Admin UI smoke (menu/ACL/filter/delete); curl/Playwright API post with bearer token; Flutter manual UAT (iOS detect + notice; Android block)  
**Target Platform**: Odoo 18 backend + Android/iOS Flutter field app  
**Project Type**: Brownfield Odoo addon + Flutter client (same delivery)  
**Performance Goals**: Audit POST returns promptly for field use; admin list searchable for typical volumes  
**Constraints**: Admin + System only for UI; authenticated mobile posts only; sudo only for create-after-JWT; no browser screenshot detection (watermark instead); Coal CBA/LARR domain unchanged; `-u bhukhadan_core` after model/view/ACL/asset changes  
**Scale/Scope**: One audit model + API + admin menu; Flutter global detector/blocker/queue/notice; Odoo backend identity watermark assets

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Spec/plan scope is explicit (packages/files); no drive-by refactors  
      — Touch `bhukhadan_core` + `bhukhadan_app` only; no dashboard/section refactors.
- [x] Odoo touch list covers models ↔ views ↔ ACL ↔ menus/actions as needed  
      — `bhu.screenshot.log` + views + ACL + menu + API controller route + web watermark assets.
- [x] Domain stays Coal CBA / LARR; no restored NH/Railway/CGLRC without ratified spec
- [x] Security/groups and sudo usage justified  
      — UI: `group_bhuarjan_admin` + `base.group_system` only (read + unlink).  
      — API create via `sudo()` after JWT `check_permission` so portal/patwari users without model ACL can still report.
- [x] Module upgrade / asset refresh called out when XML, models, or static assets change  
      — Require `-u bhukhadan_core`; Flutter rebuild/reinstall for app changes.
- [x] Complexity Tracking filled if any constitution principle is bent — N/A

## Project Structure

### Documentation (this feature)

```text
specs/003-screenshot-tracker/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── screenshot-audit-api.md
└── tasks.md              # /speckit-tasks (not this command)
```

### Source Code (repository root)

```text
bhukhadan_core/
├── models/screenshot_log.py              # NEW: bhu.screenshot.log
├── models/__init__.py                    # import screenshot_log
├── views/screenshot_log_views.xml        # NEW: list/form/search/action
├── views/menuitem.xml                    # Users → Screenshot Audit Log
├── security/ir.model.access.csv          # admin/system read+unlink
├── controllers/api/survey_api.py         # POST /api/bhukhadan/audit/screenshot
│                                         # (or dedicated audit controller if preferred)
├── static/src/js/screenshot_watermark.js # NEW: backend identity watermark mount
├── static/src/css/screenshot_watermark.css
└── __manifest__.py                       # data file + assets + version bump

bhukhadan_app/
├── lib/src/constants/api_constants.dart  # audit endpoint
├── lib/src/services/api_service.dart     # POST helper if needed
├── lib/src/services/screenshot_audit_service.dart  # NEW: detect/queue/retry/notice
├── lib/src/utils/storage.dart            # queue persistence keys
├── lib/src/app.dart / navigation         # install listener + secure flags globally
└── android/... MainActivity / theme      # FLAG_SECURE for whole app window
    ios/...                               # screenshot notification wiring if needed
```

**Structure Decision**: Keep audit API next to existing `/api/bhukhadan/*` routes for one auth pattern. Flutter uses a small dedicated service so screens stay thin. Prefer extending existing `survey_api.py` over a new controller file unless file size becomes unwieldy.

## Complexity Tracking

> No constitution violations.

## Phase 0 & Phase 1

See [research.md](./research.md), [data-model.md](./data-model.md), [contracts/screenshot-audit-api.md](./contracts/screenshot-audit-api.md), and [quickstart.md](./quickstart.md).
