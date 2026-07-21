# Data Model: Mobile App ↔ Core Sync

## Mobile Session

- **Purpose**: Represents authenticated mobile access after OTP login.
- **Source**: Existing auth controllers and token storage.
- **Key attributes**:
  - `mobile`
  - `otp_input`
  - `user_id`
  - `token`
  - `roles`
  - `expiry`
- **Validation rules**:
  - Only registered/allowed users receive a session.
  - Expired or invalid tokens cannot access survey endpoints.
- **Relationships**:
  - Belongs to one `Field User`.

## Field User

- **Purpose**: Existing BhuKhadan user performing mobile survey work.
- **Source**: `res.users` plus role/group mappings already used by mobile auth and survey access control.
- **Key attributes**:
  - `id`
  - `name`
  - `login`
  - `mobile`
  - `bhuarjan_role`
  - `groups`
- **Validation rules**:
  - User must be discoverable by primary or additional mobile number for OTP flows.
  - Survey access remains constrained by current role rules.

## Survey

- **Purpose**: Primary mobile business record created, listed, viewed, updated, and partially prefilled from Khasra search.
- **Source**: Existing `bhu.survey` plus mobile survey API helpers.
- **Key attributes in release scope**:
  - Identity/context: `id`, `name`, `survey_uuid`, `user_id`
  - Master links: `department_id`, `project_id`, `area_id`, `village_id`, `tehsil_id`
  - Land facts: `survey_date`, `survey_type`, `khasra_number`, `khata_no`, `land_acquire_year`, `total_area`, `acquired_area`
  - Site/use details: `crop_type_id`, `irrigation_type`, `distance_from_main_road`
  - Structure/water details: `has_house`, `house_type`, `house_area`, `has_shed`, `shed_area`, `has_well`, `well_type`, `well_count`, `has_tubewell`, `tubewell_count`, `has_pond`
  - Geo/status: `latitude`, `longitude`, `location_accuracy`, `location_timestamp`, `remarks`, `state`
  - Document checklist: `mb_owner_decl_date`, `mb_decl_no_claim_pending`, `mb_decl_documents_received`, `mb_decl_gps_photo_video`
  - Related collections: `landowners`, `house_owners`, `tree_lines`, `photos`
- **Out of mobile capture scope** (backend/desk): `award_structure_ids`, section objection links, rate permutations, computed workflow flags
- **Validation rules**:
  - Mobile field set is defined by `survey.py` capture sections in `survey_views.xml` (see `contracts/survey-field-parity.md`).
  - `area_id` is required before mobile `village_id` selection.
  - Chosen `village_id` must belong to the selected `project_id` and selected `area_id`.
  - Partial Khasra-prefill data may be returned, but remaining required editable fields must still be completed before final save.
  - Only editable surveys can be changed from mobile.
- **Relationships**:
  - Belongs to one `Field User`
  - Belongs to one `Project`
  - Belongs to one optional/required-in-mobile-flow `Area`
  - Belongs to one `Village`
  - May include many `Landowners`, `House Owners`, `Tree Lines`, and `Photos`

## Area

- **Purpose**: Master dropdown value used by mobile to narrow Village choices and stored on the survey.
- **Source**: `bhukhadan.area.master`
- **Key attributes**:
  - `id`
  - `name`
  - `active`
  - derived `village_count` for dropdown/help display
- **Validation rules**:
  - Only active Areas linked to project villages are offered.
  - Mobile does not create or rename Areas.
- **Relationships**:
  - One `Area` can be linked to many `Villages`
  - One `Area` can be referenced by many `Surveys`

## Village

- **Purpose**: Final location choice after Area selection in mobile survey flow.
- **Source**: `bhu.village`
- **Key attributes**:
  - `id`
  - `name`
  - `village_code`
  - `display_code`
  - `dropdown_label`
  - `area_id`
  - `project_ids`
  - `tehsil_id`
- **Validation rules**:
  - For this mobile flow, Village remains unavailable until Area is selected.
  - Only villages mapped to the selected project and selected Area are offered.
  - Villages without `area_id` are outside the selectable mobile Area flow until master data is fixed.
- **Relationships**:
  - May belong to many `Projects`
  - Belongs to zero or one `Area`
  - Can be referenced by many `Surveys`

## Khasra Prefill Result

- **Purpose**: Search result used to pre-populate survey fields before user completes the remaining form.
- **Source**: Existing survey-search/list/detail behavior using Khasra query and current survey API serialization.
- **Key attributes**:
  - `khasra_number`
  - matching survey identifiers/context
  - whichever in-scope survey fields are currently returned by the working mobile flow
- **Validation rules**:
  - Prefill may be partial.
  - Prefill cannot bypass required field validation at save time.
  - User must still be allowed to edit remaining editable fields.

## Relationship Summary

- `Field User` -> many `Surveys`
- `Project` -> many `Villages`
- `Area` -> many `Villages`
- `Project + Area` -> filtered set of `Villages`
- `Survey` -> one selected `Project`, one selected `Area`, one selected `Village`
- `Khasra Prefill Result` -> hydrates one in-progress `Survey` draft in the app
