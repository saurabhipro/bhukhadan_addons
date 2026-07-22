# Research: Screenshot Tracker

## 1. Admin UI placement and ACL

**Decision**: Menu under **Users** (alongside JWT / Mobile OTP), groups = `group_bhuarjan_admin` + `base.group_system` only. ACL: read + unlink; no create/write from UI (rows created by API).

**Rationale**: Matches clarified access; sensitive audit next to other security menus; prevents hand-edited fake logs from UI.

**Alternatives considered**: District Admin read access (rejected per clarify Q4); full CRUD for admins (rejected — create/write should be API-only).

## 2. API authentication and IP capture

**Decision**: `POST /api/bhukhadan/audit/screenshot` with existing `@check_permission` JWT gate; persist `request` client IP from `X-Forwarded-For` / `X-Real-IP` / `remote_addr`; create with `sudo()` after auth.

**Rationale**: Reuses mobile auth; IP is server-observed (spec FR-008); sudo avoids ACL gaps for Patwari/portal-style mobile users.

**Alternatives considered**: Public unauthenticated endpoint (rejected — security); requiring Internal User ACL for create (breaks mobile roles).

## 3. Flutter detection strategy

**Decision**:
- **iOS**: Use platform screenshot notification (e.g. `UIApplication.userDidTakeScreenshotNotification` via plugin/channel).
- **Android**: Prefer **window FLAG_SECURE** for whole app (blocks/obscures captures); best-effort ContentObserver/MediaStore hooks only if reliable enough — do not block UX if detection misses.
- Always attempt to report when detection fires; always show brief notice on detect.

**Rationale**: Clarifications require all-screen blocking + notice + logging; OS capabilities differ; blocking is the Android safety net.

**Alternatives considered**: Survey-only FLAG_SECURE (rejected — Q2 = all screens); silent logging (rejected — Q3 = brief notice).

## 4. Offline queue

**Decision**: Persist a FIFO queue of pending events (JSON list in SharedPreferences or small local file). On detect: enqueue + notice. On connectivity / app resume / after login: flush with exponential backoff; keep items until HTTP 2xx or max retries then keep for manual retry on next session (do not crash; do not drop on first failure).

**Rationale**: Clarify Q1 requires queue+retry.

**Alternatives considered**: Drop if offline (rejected); single fire-and-forget (rejected).

## 5. Screen naming and survey linkage

**Decision**: Maintain a lightweight “current screen” context (route name / screen label + optional `surveyId`) updated by navigation or screen `initState`. Include in POST payload as `screen_name` / `survey_id`.

**Rationale**: Spec FR-009 / FR-003; avoids empty “what” in admin list.

**Alternatives considered**: Only hard-code a few screens (incomplete); omit survey link (weaker audit).

## 6. Backend starting point

**Decision**: Implement model/views/ACL/API on current `main` from scratch (prior uncommitted stub not present on branch). Align fields with [data-model.md](./data-model.md).

**Rationale**: Repo state has no `screenshot_log` files on `main`.

**Alternatives considered**: Assume stub exists (would fail upgrade/plan).

## 7. Odoo web watermark (no browser screenshot detection)

**Decision**: Mount a fixed, `pointer-events: none`, low-opacity repeating diagonal text overlay on `web.assets_backend` using `@web/session` (`name`, `username`/`login`, `uid`). Do **not** POST to `bhu.screenshot.log` from the browser. Pattern similar to other backend overlays (`login_as_banner` / terms gate) but non-interactive and always on for signed-in backend.

**Rationale**: Spec clarification — browsers cannot log Print Screen; watermark enables post-leak attribution. Keeps audit log honest (mobile-only detections).

**Alternatives considered**: Fake “screenshot taken” JS hooks (unreliable/false sense of security); watermark only on sensitive menus (weaker; user asked for web coverage); server-side PDF watermark only (misses live UI screenshots).
