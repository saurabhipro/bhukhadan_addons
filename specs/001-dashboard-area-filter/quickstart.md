# Quickstart: Dashboard Area Filter

## Prerequisites

- Odoo 18 with `bhukhadan_core` installed
- At least one Project with multiple Villages
- Area Master records created (Master Data → Area Master)
- Villages assigned an Area on the Village form

## Upgrade after implementation

```bash
odoo-bin -c /etc/odoo18.conf -d YOUR_DB -u bhukhadan_core --stop-after-init
```

Hard-refresh browser assets (Ctrl+Shift+R).

## Validation scenarios

### 1. Cascade happy path

1. Open **Admin Dashboard** (or SDM).
2. Select Department (if shown) and a **Project**.
3. Confirm **Area** dropdown appears and lists areas for that project’s villages.
4. Select an **Area**.
5. Confirm **Village** enables and lists only villages for that Area.
6. Select a Village → dashboard content loads as today.

**Expected**: Village options never include villages from other Areas.

### 2. Clear / change guards

1. With Project+Area+Village selected, change **Area**.
2. **Expected**: Village clears if not in the new Area; list refreshes.
3. Change **Project**.
4. **Expected**: Area and Village clear; Area list reloads for new Project.

### 3. Persistence

1. Select Project+Area+Village; reload the page/dashboard.
2. **Expected**: Same Project/Area/Village restore when still valid.

### 4. Master data

1. Open a Village without Area → set Area → Save.
2. On dashboard, select Project containing that Village and the new Area.
3. **Expected**: Village appears under that Area.

## Out of scope for this validation

- Area-level KPI aggregation in stats cards
- Auto-syncing Survey.`area_id` from Village.`area_id`
