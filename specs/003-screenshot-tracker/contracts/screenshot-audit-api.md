# Contract: Screenshot Audit API

**Backend**: `bhukhadan_core`  
**Client**: `bhukhadan_app` (Flutter)  
**Auth**: `Authorization: Bearer <jwt>` via existing mobile login

## `POST /api/bhukhadan/audit/screenshot`

**Purpose**: Record a screenshot event for administrator audit.

### Request body (JSON)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `screen_name` | string | no | Current app screen/page label |
| `platform` | string | no | `android` \| `ios` \| `web` \| `linux` \| `windows` \| `macos` \| `unknown` |
| `survey_id` | int | no | Related survey when on survey UI |
| `device_info` | string | no | Device / OS summary |
| `notes` | string | no | Optional |

### Success response

- Status: `201`
- Body shape:
```json
{
  "success": true,
  "message": "Screenshot event logged",
  "data": {
    "id": 1,
    "user_id": 15,
    "ip_address": "203.0.113.10",
    "event_time": "2026-07-22 16:00:00"
  }
}
```

### Error responses

| Status | When |
|--------|------|
| 401/403 | Missing/invalid bearer token |
| 400 | Invalid JSON |
| 500 | Unexpected server error |

### Server responsibilities

- Resolve user from JWT.
- Capture client IP (proxy headers when present).
- Snapshot login/mobile/role when available.
- Ignore invalid `survey_id` (store without survey rather than fail).

### Client responsibilities

- Call only when signed in (or flush queue after login).
- Include current `screen_name` / `survey_id` when known.
- On detect: show brief non-blocking notice; enqueue if offline; retry until success.
- Apply app-wide screenshot blocking where OS supports it.
- Never crash the app on report failure.

## Admin UI (non-HTTP contract)

- Menu: **Users → Screenshot Audit Log**
- Groups: BhuKhadan Administrator, System
- Views: list + form + search (filter user/IP/screen/date; group by user/IP/platform/screen)
- List/form: no create/edit; delete allowed for those groups
