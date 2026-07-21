# Feature Specification: Dashboard Area Filter

**Feature Branch**: `001-dashboard-area-filter`  
**Created**: 2026-07-21  
**Status**: Draft  
**Input**: User description: "I want to add another dropdown called Area… after I select the Area the Village should come"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Select Area then Village on dashboard (Priority: P1)

As an admin/SDM/collector/district user on the role dashboard header filters, after I choose a **Department** (when shown) and **Project**, I see an **Area** dropdown. When I select an Area, the **Village** dropdown enables/refreshes and lists only villages that belong to that Area (within the selected Project).

**Why this priority**: Matches the requested UX and unblocks scoped work by Area before Village.

**Independent Test**: On Admin (or SDM) dashboard, select Project → Area → confirm Village list is filtered; clear Area and confirm Village list resets appropriately.

**Acceptance Scenarios**:

1. **Given** a Project is selected and Areas exist for that Project, **When** the header renders, **Then** an Area dropdown appears between Project and Village, Village stays disabled/empty until Area is chosen (or shows placeholder “Village”).
2. **Given** Project + Area selected, **When** Area changes, **Then** Village options reload to villages linked to that Area under the Project, and any previously selected Village that is not in the new list is cleared.
3. **Given** Project selected but Area not selected, **When** user opens Village, **Then** Village remains disabled or empty (no full-project village list until Area is chosen).

---

### User Story 2 - Persist Area selection like Project/Village (Priority: P2)

As a returning user, my last selected Area for that dashboard type is restored from local storage (same pattern as Project/Village), and Village restores only if still valid for the restored Area.

**Why this priority**: Consistency with existing filter UX; avoids re-picking Area every visit.

**Independent Test**: Select Project+Area+Village, reload dashboard, confirm selections restore when still valid.

**Acceptance Scenarios**:

1. **Given** Area was selected previously, **When** the dashboard loads with a valid Project, **Then** Area is restored and Villages load for that Area.
2. **Given** restored Area is invalid for current Project, **When** filters load, **Then** Area and Village clear safely.

---

### User Story 3 - Maintain Area master data (Priority: P3)

As an admin/district administrator, I can assign an Area on Village master (and keep existing Area on Survey) so dashboard filtering has a durable Area→Village relationship.

**Why this priority**: Required data foundation; Area master already exists but Village has no Area link today.

**Independent Test**: Open Village form, set Area, save; that Village appears under that Area on the dashboard for a Project that includes it.

**Acceptance Scenarios**:

1. **Given** Area Master records exist, **When** I set `Area` on a Village and save, **Then** the Village is available under that Area in the dashboard filter for Projects containing it.
2. **Given** a Village has no Area, **When** an Area is selected on the dashboard, **Then** that Village does not appear in the Village list.

### Edge Cases

- Project with no villages → Area list empty; Village disabled.
- Project villages with no `area_id` → Area dropdown may be empty or only show Areas that appear; Villages without Area never appear under a selected Area.
- Changing Project clears Area and Village.
- Changing Area clears Village if it is not in the new Area’s villages.
- Survey still has its own `area_id` (independent field); this feature does not require rewriting historical survey areas unless a follow-up migration is approved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Dashboard header filter order is Department (if shown) → Project → **Area** → Village.
- **FR-002**: Area dropdown is enabled only when a Project is selected.
- **FR-003**: Village dropdown is enabled only when an Area is selected (after Project).
- **FR-004**: Selecting Area loads Villages for that Area within the selected Project’s `village_ids`.
- **FR-005**: Backend provides Areas for a Project and Villages for Project+Area (RPC methods on `bhuarjan.dashboard`).
- **FR-006**: `bhu.village` gains optional `area_id` → `bhukhadan.area.master` for master linkage.
- **FR-007**: Area/Village selection persistence uses existing localStorage prefix pattern per dashboard type.
- **FR-008**: Feature applies to dashboards that already show Project + Village filters (Admin, SDM, Collector, District, Department as configured).
- **FR-009**: No restoration of removed NH/Railway/CGLRC acts; scope limited to dashboard filters + village master.

### Key Entities

- **Area Master** (`bhukhadan.area.master`): existing master (name, active).
- **Village** (`bhu.village`): gains `area_id` link to Area.
- **Project** (`bhu.project`): existing `village_ids`; Areas derived from those villages’ `area_id`.
- **Dashboard filters** (OWL header): Department / Project / Area / Village cascade.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With Project selected, user can pick Area then Village in ≤2 clicks after options load.
- **SC-002**: Village list after Area selection contains only villages with that `area_id` among the Project’s villages (100% filter correctness on sample data).
- **SC-003**: Changing Project or Area never leaves a Village selection that is outside the current cascade.
- **SC-004**: Module upgrade applies Village `area_id` field and views without errors; existing Project→Village flow remains available once Area is set on villages.
