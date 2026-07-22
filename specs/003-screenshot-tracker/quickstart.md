# Quickstart: Screenshot Tracker

## Goal

Validate admin audit UI + mobile screenshot reporting (who / screen / when / IP), offline queue, brief notice, app-wide screenshot blocking, and Odoo web identity watermark.

**Upgrade required**: after deploying this feature, run Odoo with `-u bhukhadan_core` so the new model, ACL, views, menu, and **backend assets** (watermark CSS/JS) load. Hard-refresh the browser (or clear assets) if the watermark does not appear.

## Prerequisites

- Odoo with `bhukhadan_core` upgraded after this feature (`-u bhukhadan_core`)
- Admin user in BhuKhadan Administrator (or System)
- Field mobile user with OTP login
- Flutter app build including screenshot audit service
- Optional: Playwright/`curl` with bearer token

## Backend validation

1. As Administrator, open **Users → Screenshot Audit Log** — list loads (may be empty).
2. As District Admin / Patwari web user, confirm menu is **not** visible.
3. Obtain mobile JWT (OTP login).
4. `POST /api/bhukhadan/audit/screenshot` with bearer token and sample body (`screen_name`, `platform`, optional `survey_id`).
5. Expect `201` and a new admin list row with **user**, **IP**, **time**, **screen**.
6. Open form detail — identity snapshots and IP present.
7. Delete the row as admin — it disappears.
8. Repeat POST **without** token — expect auth failure; no new trusted row.
9. As any signed-in backend user, confirm a faint identity watermark (name/login) is visible and does not block clicks; take an OS screenshot and confirm watermark text is readable in the image.

## Mobile validation

1. Sign in on device/emulator.
2. Navigate across home and survey screens — screenshot blocking active where OS allows (Android: blank/blocked capture).
3. On a detection-capable platform (prefer iOS): take a screenshot.
4. Confirm brief **recorded** notice (non-blocking).
5. Within ~30s online, admin list shows the event with correct user/screen/IP.
6. Airplane mode → screenshot → notice still shows → restore network → event eventually appears (queue/retry).
7. Expired/logged-out session should not create anonymous trusted rows; app must not crash.

## Platform / watermark limits

- Browser Print Screen is **not** logged as `bhu.screenshot.log` rows; web uses identity watermark only.
- Android prioritizes `FLAG_SECURE` blocking; iOS prioritizes detection + notice + API report.
- Cropping or heavy editing of a screenshot may remove watermark text.

## Expected outcomes

- Admin can identify who / what / when / IP in under a minute for a known test event.
- Non-admin roles cannot open the audit UI.
- Authenticated reports appear in the log; unauthenticated do not.
- Offline events retry; user sees a brief notice on detect.
- Odoo web screenshots show the signed-in user’s watermark (no browser audit-log row expected).

## References

- [Spec](./spec.md)
- [Plan](./plan.md)
- [Data model](./data-model.md)
- [API contract](./contracts/screenshot-audit-api.md)
