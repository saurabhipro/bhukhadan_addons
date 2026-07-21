# Quickstart: Mobile App ↔ Core Sync

## Goal

Validate that the BhuKhadan mobile app and `bhukhadan_core` mobile APIs work together for:
- OTP login
- survey list/detail/create/update
- Khasra-prefill
- Project → Area → Village dropdown flow

## Prerequisites

- Odoo instance running with this repo in `addons_path`
- Module upgraded after backend changes: `-u bhukhadan_core`
- A test mobile user with valid role/group access
- At least one project with:
  - linked villages
  - villages mapped to active Areas
- Mobile app build/source available for same-delivery validation

## Backend Validation

1. Request OTP using a registered mobile number.
2. Login with OTP and capture the bearer token.
3. Call survey list endpoint with the token and verify only authorized survey rows appear.
4. Query survey search/list using a known Khasra value and confirm the response includes expected prefill fields.
5. Verify project-scoped Area choices are available using the master-data contract for the selected project.
6. Verify Village options do not load until Area is chosen, then return only villages linked to the selected Area.
7. Create a survey including:
   - existing working survey baseline fields
   - `area_id`
   - a valid `village_id` for the chosen Project + Area
8. Fetch survey detail and confirm:
   - Area is preserved
   - Khasra-prefilled values remain populated
   - user-entered remaining fields are saved
9. Update an editable survey and confirm invalid/expired token requests fail safely.

## Mobile App (Flutter) Validation

1. Sign in from `bhukhadan_app` with the test mobile user.
2. Walk each survey section mirroring `survey_views.xml` (see field-parity matrix).
3. Confirm **Area** dropdown and Project → Area → Village cascade.
4. Search by Khasra; verify returned fields prefill across sections.
5. Complete remaining fields including document checklist (`mb_*`), trees, photos, GPS.
6. Save and reopen — values must match backend survey form.
7. Run parity matrix: zero **Gap** rows for mobile-capture fields.

## Expected Outcomes

- Login succeeds for valid users and fails cleanly for invalid ones.
- Project → Area → Village cascade is enforced.
- Khasra search pre-fills available fields without locking the user out of completing the form.
- Surveys created or updated from mobile match backend data for all in-scope fields.
- No known in-scope mobile field is silently dropped between app, API payload, and backend persistence.

## References

- [Spec](./spec.md)
- [Plan](./plan.md)
- [Research](./research.md)
- [Data Model](./data-model.md)
- [Contract](./contracts/mobile-app-core-api.md)
- [Field parity matrix](./contracts/survey-field-parity.md)
