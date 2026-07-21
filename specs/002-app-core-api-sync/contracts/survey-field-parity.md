# Survey Field Parity Matrix (Mobile)

**Source of truth**: `bhukhadan_core/models/survey/survey.py` + `views/survey_views.xml`  
**Clients**: mobile API (`utils/survey_api.py`) + **Flutter** `bhukhadan_app` survey screens

Legend:
- **M** = must be captured/displayed on mobile
- **P** = prefilled from Khasra search when available
- **R** = read-only on mobile (display only)
- **B** = backend/desk only (out of mobile UI scope)
- **Gap** = not yet in API serialize/write path and must be added in this feature

## Header / context

| Field | Mobile | API write | API read | Flutter UI | Notes |
|-------|--------|-----------|----------|------------|-------|
| `project_id` | M | yes | yes | update | Project dropdown |
| `department_id` | M | yes | yes | update | Often derived from project |
| `survey_date` | M | yes | yes | update | |
| `survey_type` | M | yes | yes | update | rural/urban |
| `area_id` | M | yes | yes | update | Project → Area → Village cascade |
| `village_id` | M | yes | yes | update | Enabled only after Area |
| `tehsil_id` | M/P | yes | yes | update | May prefill from village |
| `company_id` | R | no | partial | display | District; usually derived |
| `district_name` | R | no | yes | display | |
| `user_id` | R | no | yes | display | Patwari |
| `name`, `survey_uuid` | R | no | yes | display | System-generated |
| `state`, `payment_status` | R | state yes | yes | display | Workflow status |

## Land tab (Survey page)

| Field | Mobile | API write | API read | Flutter UI | Notes |
|-------|--------|-----------|----------|------------|-------|
| `khasra_number` | M/P | yes | yes | update | Search key; prefill source |
| `khata_no` | M/P | yes | yes | update | |
| `land_acquire_year` | M/P | yes | yes | update | |
| `total_area` | M/P | yes | yes | update | |
| `acquired_area` | M/P | yes | yes | update | |
| `has_traded_land` | M/P | yes | yes | update | |
| `traded_land_area` | M/P | yes | yes | update | Visible when traded=yes |
| `distance_from_main_road` | M/P | yes | yes | update | |
| `crop_type_id` | M/P | yes | yes | update | Land type master |
| `irrigation_type` | M/P | yes | partial | update | In model; confirm UI exposure |
| `has_house`, `house_type`, `house_area` | M/P | yes | yes | update | Conditional on has_house |
| `has_shed`, `shed_area` | M/P | yes | yes | update | |
| `has_well`, `well_type`, `well_count` | M/P | yes | yes | update | |
| `has_tubewell`, `tubewell_count` | M/P | yes | yes | update | |
| `has_pond` | M/P | yes | yes | update | |
| `remarks` | M/P | yes | yes | update | |
| `latitude`, `longitude` | M/P | yes | yes | update | GPS capture |
| `location_accuracy`, `location_timestamp` | M/P | yes | yes | update | GPS metadata |
| `survey_image` | M | via photos | optional | update | Prefer `photos[]` API |
| `land_type_for_award` | B | **Gap** | **Gap** | skip | Award desk flow |

## Related records

| Entity | Mobile | API | Flutter UI | Notes |
|--------|--------|-----|------------|-------|
| `landowner_ids` | M/P | yes | update | Inline/list capture |
| `house_owner_ids` | M/P | yes | update | |
| `tree_line_ids` | M/P | yes | update | tree_master, stage, girth, qty |
| `photo_ids` / `photos[]` | M | yes | yes | update | S3 photo upload flow |

## Document checklist (Measuring Book)

| Field | Mobile | API write | API read | Flutter UI | Notes |
|-------|--------|-----------|----------|------------|-------|
| `mb_owner_decl_date` | M | yes | yes | update | Document checklist screen |
| `mb_decl_no_claim_pending` | M | yes | yes | update | |
| `mb_decl_documents_received` | M | yes | yes | update | |
| `mb_decl_gps_photo_video` | M | yes | yes | update | |

## Backend-only (not mobile capture)

| Field / section | Reason |
|-----------------|--------|
| `award_structure_ids` | Award desk workflow |
| `section15_objection_*` | Section workflow |
| `rate_permutation_ids` | Rate/award engine |
| Computed counts (`landowner_count`, `tree_detail_count`, …) | Display-only aggregates |
| `is_*_readonly`, workflow flags | UI state on backend |

## Flutter screen map (target)

Mirror `survey_views.xml` notebook sections in `bhukhadan_app`:

1. **Survey controls** — type, payment badge (read-only)
2. **Project + location** — project, department, date, **area**, village, tehsil
3. **Land** — khasra through distance/road
4. **Crop** — land type / irrigation
5. **House + infrastructure** — house, shed, well, tubewell, pond
6. **Remarks + GPS**
7. **Landowners** tab
8. **House owners** tab
9. **Document checklist** tab — `mb_*` declaration fields
10. **Trees** tab
11. **Photos** tab

Khasra search pre-fills any returned fields across sections 2–6; user completes gaps before save.
