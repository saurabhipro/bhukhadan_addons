# Research: Mobile App ↔ Core Sync

## Decision 1: Reuse existing mobile auth flow

- **Decision**: Keep the current OTP/JWT login flow as the mobile authentication baseline and align the app to it rather than introducing a new auth method.
- **Rationale**: `auth.py` already supports OTP request and login, returns a bearer token plus user metadata, and downstream survey endpoints already rely on the same token gate.
- **Alternatives considered**:
  - Add a second login mechanism just for the new app flow: rejected because it increases support and security risk.
  - Move to website/session auth: rejected because the mobile APIs already expect bearer-token usage.

## Decision 2: Use `survey.py` + `survey_views.xml` as the mobile field source of truth

- **Decision**: Flutter survey screens and the mobile API must align with all **field-capture** sections on the backend survey form, not only the subset currently in `SURVEY_WRITABLE`.
- **Rationale**: User confirmed mobile screens will be updated per `survey.py`; Khasra prefill covers some fields but the rest must be editable in the app.
- **Alternatives considered**:
  - Keep only today's API subset: rejected — leaves `area_id` read gaps, `mb_*` checklist, and other form fields uncaptured.
  - Duplicate a new mobile-only field list: rejected — `survey_views.xml` already defines the canonical layout.

## Decision 3: Add Project → Area → Village master-data flow for mobile

- **Decision**: Mobile must follow the same Area gating rule as the new web dashboard: user selects Project, then Area, then Village.
- **Rationale**: The spec clarification resolved this explicitly, and `village.area_id` plus dashboard project/area/village helpers already establish the canonical relationship.
- **Alternatives considered**:
  - Keep Village project-wide and make Area optional: rejected by clarification.
  - Make Area required but not filter Village: rejected because it weakens data integrity.

## Decision 4: Reuse existing Area/Village lookup logic instead of inventing a separate mobile-only source

- **Decision**: Reuse or mirror `get_areas_by_project()` and `get_villages_by_project(project_id, area_id)` logic for mobile master-data endpoints/contracts.
- **Rationale**: Those methods already express the desired Area/Village rules and rely on live master data (`project.village_ids`, `village.area_id`, `active=True`).
- **Alternatives considered**:
  - Query `bhu.survey` records to derive Areas/Villages: rejected because villages without surveys would disappear.
  - Hardcode master lists in the app: rejected because live Odoo data must stay authoritative.

## Decision 5: Khasra search remains a prefill aid, not a final-save replacement

- **Decision**: When the app searches by Khasra, it should prefill whatever fields the current survey flow returns, and leave the rest editable for the user.
- **Rationale**: This matches the user clarification and preserves today’s field-capture workflow rather than forcing full auto-completion.
- **Alternatives considered**:
  - Require Khasra search to return a complete survey payload: rejected because partial data is a known case.
  - Ignore Khasra-prefill in this release: rejected because the user called it out directly.

## Decision 6: Same-release delivery must include Flutter app + backend contract alignment

- **Decision**: Plan for API gap closure in `bhukhadan_core` **and** Flutter (`bhukhadan_app`) survey screen updates in the same release.
- **Rationale**: User confirmed same-delivery app updates and full field capture; Flutter is the mobile client.
- **Alternatives considered**:
  - Backend-only release: rejected.
  - Spec-only handoff: rejected.

## Decision 7: Preserve current access-control pattern and tighten validation where needed

- **Decision**: Keep the current `check_permission` bearer-token gate and survey access-domain checks, but include validation for Project/Area/Village consistency in the mobile flow.
- **Rationale**: Constitution requires authenticated/authorized APIs. The existing token check plus `api_user_can_access_survey()` and domain builders are the right base; the new Area cascade adds one more consistency rule.
- **Alternatives considered**:
  - Broaden access with looser mobile rules: rejected by constitution.
  - Add unrestricted public master-data endpoints: rejected because project-scoped choices should stay within authenticated flows.
