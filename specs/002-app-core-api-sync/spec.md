# Feature Specification: Mobile App ↔ Core Sync

**Feature Branch**: `002-app-core-api-sync`

**Created**: 2026-07-21

**Status**: Draft

**Input**: User description: "i want to link the bhukhadan_app with the bhukhadan_core api like login, survey api as new fields are created ..also add area drop down as well ..also"

## Clarifications

### Session 2026-07-21

- Q: How should Area interact with Village on mobile? → A: Require Area first; Village list filtered by selected Area (dashboard-style cascade).
- Q: Where will app UI changes be delivered? → A: `bhukhadan_app` source will be shared and updated in the same delivery.
- Q: What is the scope beyond Area for this release? → A: Use the existing survey API fields as the baseline; Khasra search pre-fills returned fields and the user updates the rest.
- Q: Should mobile capture all survey fields from core? → A: Yes — Flutter survey screens must align with `survey.py` / `survey_views.xml` field-capture sections; close API gaps where fields are missing from mobile serialize/write paths.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sign in on the mobile app (Priority: P1)

A registered field user (for example a Patwari) opens the BhuKhadan mobile app, signs in with their approved credentials (mobile OTP and/or password login as already supported for the app), and reaches a usable home/survey workspace without using the web backend.

**Why this priority**: Without reliable login, no survey or Area work on the app can succeed.

**Independent Test**: A registered test user can complete sign-in on the app against the live BhuKhadan environment and see an authenticated session; an unregistered number is refused with a clear message.

**Acceptance Scenarios**:

1. **Given** a registered user with a valid mobile number, **When** they request and confirm OTP (or complete password login where enabled), **Then** they are signed in and can open survey flows.
2. **Given** an unknown mobile number, **When** they attempt sign-in, **Then** the app shows a clear failure and does not grant access.
3. **Given** an expired or invalid session, **When** they try to create or list surveys, **Then** they are prompted to sign in again.

---

### User Story 2 - Create and retrieve surveys with current core fields (Priority: P1)

After sign-in, the field user creates, lists, opens, and updates surveys so that every survey field the organization currently expects on the mobile workflow—including fields recently added in core—is available on the app and stored correctly in BhuKhadan.

**Why this priority**: Survey capture is the primary mobile job; field parity with core prevents data loss and duplicate desk entry.

**Independent Test**: Create a survey from the app including required masters and new fields; open the same survey in the backend and confirm values match; list surveys for the signed-in user and open one for edit where allowed.

**Acceptance Scenarios**:

1. **Given** an authenticated field user and valid project/village context, **When** they submit a new survey with all required mobile fields, **Then** the survey appears in BhuKhadan with matching values.
2. **Given** existing surveys for that user, **When** they refresh the survey list, **Then** they see their surveys with accurate summary details.
3. **Given** a survey still editable under current business rules, **When** they update a field from the app, **Then** the change is saved and visible on reopen (app and backend).
4. **Given** a new survey field has been introduced in core for the mobile workflow, **When** the app and mobile services are updated for this feature, **Then** that field can be sent and returned without silent drop.
5. **Given** the user searches for a Khasra in the mobile survey flow, **When** matching survey data is available from the existing survey API field set, **Then** returned fields are pre-filled and the user completes the remaining editable fields before save.

---

### User Story 3 - Area dropdown on mobile survey flow (Priority: P2)

While creating or editing a survey on the mobile app, the user selects an **Area** from a dropdown (options appropriate to their project/context), then proceeds with village and other survey details. Area selection is saved on the survey and visible later in the app and backend.

**Why this priority**: Area is an explicit product ask and aligns field capture with master data and web dashboard Area usage; it depends on working login and survey save/load.

**Independent Test**: With Areas and villages configured for a project, create a survey from the app selecting Area; confirm Area is stored and shown on detail; confirm Village stays unavailable until Area is selected and then only shows villages from that Area.

**Acceptance Scenarios**:

1. **Given** a project that has Areas linked to its villages, **When** the user opens the Area control, **Then** they see those Areas (active only) in a selectable list.
2. **Given** an Area is selected, **When** they continue to Village, **Then** only villages linked to that Area are available for selection.
3. **Given** no Area has been selected yet, **When** the user reaches the Village field, **Then** Village remains disabled until Area is chosen.
4. **Given** a survey saved with an Area, **When** they reopen the survey, **Then** the same Area is shown and can be changed while the survey remains editable.
5. **Given** no Areas exist for the selected project, **When** the user reaches Area selection, **Then** they see an empty list and a clear explanation (they cannot invent Area names on the device).

---

### User Story 4 - Keep app and core aligned when fields change (Priority: P3)

When core adds or changes survey/master fields that belong in the mobile workflow, product and engineering have a clear expectation: mobile sign-in and survey create/list/detail/update stay aligned so the app does not silently ignore new required data.

**Why this priority**: Prevents recurring “app is behind core” gaps after Area and future masters.

**Independent Test**: For this release, Area (and any other fields named in scope) pass a field-parity checklist between core mobile services and the app screens; documented process exists for the next field addition.

**Acceptance Scenarios**:

1. **Given** a newly in-scope survey field for mobile, **When** the parity checklist is run, **Then** create, read, and update paths all carry that field end-to-end.
2. **Given** a field is out of mobile scope, **When** the app is used, **Then** the app does not claim to support it.

---

### Edge Cases

- User loses connectivity mid-save: app shows a recoverable error; no partial silent success unless offline mode is explicitly in scope (assumed out of scope for this feature).
- Session expires during survey entry: user must re-authenticate; draft behavior is unchanged unless already productized.
- Project has villages without Area assigned: those villages are not selectable in the mobile Area→Village flow until master data is completed.
- Inactive Area: does not appear in the Area dropdown.
- Unauthorized user tries another user’s survey: access is denied with a clear error.
- Khasra search returns only partial data: returned fields are pre-filled and the remaining required fields stay editable for the user to complete.
- Trailing incomplete ask (“also …”): treated as Area dropdown plus field-parity process unless clarifications expand scope.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Registered field users MUST be able to sign in to the BhuKhadan mobile app using the organization’s existing mobile authentication flows (OTP and/or password as currently offered to the app).
- **FR-002**: After sign-in, users MUST be able to create, list, view, and update surveys through the mobile app against BhuKhadan, subject to existing editability and role rules.
- **FR-003**: Survey create/update/detail on mobile MUST accept and return all **field-capture** survey fields defined in `bhukhadan_core/models/survey/survey.py` and shown on the backend survey form (`survey_views.xml`), including **Area**, GPS, document checklist (`mb_*`), landowners, house owners, trees, and photos — excluding backend-only workflow/award sections.
- **FR-004**: The mobile survey form MUST provide an **Area** dropdown populated from active Areas relevant to the user’s selected project (or equivalent project context on the form).
- **FR-005**: Selecting Area MUST be required before Village selection, and the Village list MUST be filtered to villages linked to the selected Area.
- **FR-006**: When core introduces additional mobile-relevant survey or master fields, the mobile app and supporting mobile services MUST be updated together so values are not silently dropped (parity checklist for this feature includes Area; future fields follow the same rule).
- **FR-007**: Unauthenticated or unauthorized mobile requests MUST be rejected without exposing other users’ survey data.
- **FR-008**: Work in this repository MUST cover any gaps in BhuKhadan mobile services and contracts needed for login, survey, Area options, and field parity; mobile app UI changes are required for acceptance even if the app lives outside this repo.
- **FR-009**: The **Flutter** mobile app (`bhukhadan_app`) MUST be updated in the same delivery: survey screens, dropdowns, Khasra prefill, and payloads aligned with `survey.py` and the mobile API contract.
- **FR-010**: A field-parity matrix (`contracts/survey-field-parity.md`) MUST be maintained; any field marked mobile-capture with an API **Gap** must be closed in `bhukhadan_core` before release.
- **FR-012**: Flutter survey UI MUST mirror backend survey form sections (project/location, land, crop, house/infrastructure, remarks/GPS, landowners, house owners, document checklist, trees, photos) with the Project → Area → Village cascade on location fields.
- **FR-011**: When a user searches by Khasra, the app MUST pre-fill any fields returned by the existing survey flow and keep the remaining editable fields available for user entry or correction before saving the survey.

### Key Entities

- **Field user**: Registered BhuKhadan user who works primarily via the mobile app.
- **Mobile session**: Authenticated access granting survey operations for that user.
- **Survey**: Field land/survey record created or updated from the app; includes masters such as project, village, and Area.
- **Area**: Master geographic/grouping unit selectable on survey; linked to villages in core master data where configured.
- **Project / Village**: Existing masters that contextualize which Areas and villages the user may choose.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A registered test field user can complete mobile sign-in and open the survey workspace in under 2 minutes on a normal network.
- **SC-002**: 100% of surveys created from the app in UAT for this feature show matching Area (and other in-scope fields) when opened in the backend.
- **SC-003**: At least 95% of UAT create/list/open/update survey attempts by authorized users succeed on first try when masters are preconfigured.
- **SC-004**: Field users can select Area from a dropdown and save it without desk-side re-entry for Area on those surveys.
- **SC-005**: Field-parity matrix shows zero **Gap** items for mobile-capture fields before release sign-off.
- **SC-006**: Flutter app UAT confirms every mobile-capture field from `survey.py` can be entered or prefilled and matches backend on reopen.

## Assumptions

- Existing mobile authentication (OTP / login) and survey create/list/detail/update services in BhuKhadan are the baseline; this feature closes gaps and aligns the app rather than inventing a second parallel auth system.
- Area master data and village–Area links are maintained in BhuKhadan (as with the dashboard Area filter work); the app does not create new Area masters.
- Villages without an Area assignment are outside the selectable mobile flow until master data is corrected.
- The mobile app source repository/path will be available during implementation so same-release UI updates can be completed and validated.
- Offline-first sync, push notifications, and APK distribution changes are out of scope unless later clarified.
- Hindi/English labels for Area follow existing bilingual master naming where the app already shows bilingual labels.
- The incomplete trailing “also” does not expand scope until clarified; default delivery is login + survey parity + Area dropdown.
- Existing Khasra search behavior remains part of the mobile survey flow; this release extends it by preserving returned values and letting users complete the remaining fields.
- Web dashboard Area filter (`001-dashboard-area-filter`) is complementary; this feature focuses on mobile app and mobile services alignment.
