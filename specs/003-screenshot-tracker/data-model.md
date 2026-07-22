# Data Model: Screenshot Tracker

## Entity: Screenshot Audit Event (`bhu.screenshot.log`)

Represents one mobile screenshot detection reported to the server.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `event_time` | Datetime | yes | When detected/reported; default now; indexed |
| `user_id` | Many2one `res.users` | yes | Actor; cascade on delete |
| `user_login` | Char | no | Snapshot at event time |
| `user_mobile` | Char | no | Snapshot |
| `user_role` | Char | no | e.g. `bhuarjan_role` snapshot |
| `ip_address` | Char | no | Server-observed client IP; indexed |
| `user_agent` | Char | no | Truncated UA string |
| `platform` | Selection | no | android/ios/web/linux/windows/macos/unknown |
| `screen_name` | Char | no | App screen/page label; indexed |
| `survey_id` | Many2one `bhu.survey` | no | set null on survey delete |
| `device_info` | Char | no | Device model/OS label |
| `notes` | Text | no | Optional free text |
| `raw_payload` | Text | no | Truncated JSON of client body for support |
| `display_name` | Char (computed) | — | `{user} @ {ip} — {screen} ({time})` |

**Ordering**: `event_time desc, id desc`  
**Rec name**: `display_name`

## Relationships

- Many events → one `res.users`
- Many events → optional one `bhu.survey`

## Validation / Rules

- Create only via authenticated mobile API (UI create disabled).
- UI edit disabled; admins may unlink (delete).
- Access: Administrator + System read/unlink only.
- Missing `screen_name` / `survey_id` allowed (store blank/False).

## Lifecycle

1. Mobile detects screenshot → queue locally if needed → POST API.  
2. Server creates row with user snapshots + IP.  
3. Admin lists/filters/opens/deletes rows.  
4. No automatic purge.
