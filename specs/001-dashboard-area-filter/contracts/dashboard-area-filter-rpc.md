# Contract: Dashboard Area Filter RPCs

**Model**: `bhuarjan.dashboard` (existing)  
**Client**: `bhukhadan_core/static/src/dashboard/js/unified_dashboard.js`

## `get_areas_by_project(project_id)`

**Purpose**: Areas available for the selected project.

**Input**:
- `project_id` (int) — required

**Output**: `list[dict]` sorted by name, each item:
```json
{
  "id": 1,
  "name": "Area North",
  "dropdown_label": "Area North",
  "village_count": 3
}
```

**Rules**:
- Invalid/missing project → `[]`
- Only Areas linked via `project.village_ids.area_id` and `active=True`
- `village_count` = count of project villages with that `area_id`

## `get_villages_by_project(project_id, area_id=None)` (extend)

**Purpose**: Villages for Project, optionally filtered by Area.

**Input**:
- `project_id` (int) — required
- `area_id` (int|false|None) — when set, filter `village.area_id == area_id`

**Output**: Same shape as today (`id`, `name`, `village_type`, `village_code`, `display_code`, `dropdown_label`).

**Rules**:
- Still restricted to `project.village_ids`
- When `area_id` provided and valid → only villages with that area
- When `area_id` missing → current behavior (all project villages) for backward compatibility; **dashboard UI will pass area_id once Area is selected**

## Client cascade contract

| Event | State updates |
|-------|----------------|
| Project change | clear Area + Village; load Areas; Village disabled |
| Area change | clear Village if invalid; load Villages(project, area) |
| Village change | set selectedVillage; refresh stats as today |

Header markup order: Project select → Area select → Village select.
