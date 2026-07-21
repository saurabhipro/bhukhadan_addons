# Data Model: Dashboard Area Filter

## Entities

### `bhukhadan.area.master` (existing)

| Field | Type | Notes |
|-------|------|--------|
| name | Char | Required, unique |
| active | Boolean | Default True |
| village_ids | One2many (optional inverse) | `bhu.village.area_id` |

### `bhu.village` (extend)

| Field | Type | Notes |
|-------|------|--------|
| area_id | Many2one → `bhukhadan.area.master` | Optional, `ondelete='restrict'` or `set null`; tracking optional |

**Validation**: No hard required Area on Village for backward compatibility (existing villages may be empty until masters are filled).

### `bhu.project` (unchanged)

- Continues to own `village_ids`.
- Areas for dropdown = distinct `village_ids.mapped('area_id')` (active areas only).

### `bhu.survey` (unchanged for MVP)

- Keeps existing `area_id`.
- No automatic sync Village.area_id ↔ Survey.area_id in MVP (document as future optional helper).

## Relationships

```text
Project --M2M--> Village --M2O--> Area Master
Survey  --M2O--> Area Master   (existing; independent of Village.area_id for MVP)
```

## State / cascade rules (UI)

1. Project cleared → clear Area, clear Village, empty both lists.
2. Area cleared → clear Village, empty Village list (or disabled).
3. Area changed → reload Villages; drop Village if not in new list.
4. Persistence keys (per dashboard `localStoragePrefix`): `_area`, `_area_name` alongside existing project/village keys.
