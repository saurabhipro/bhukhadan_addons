# Contract: Mobile App ↔ Core API Sync

**Backend**: `bhukhadan_core` mobile auth + survey services  
**Client**: `bhukhadan_app`  
**Goal**: Keep login, survey field parity, Khasra-prefill behavior, and Project → Area → Village selection aligned in one release.

## 1. Authentication

### `POST /api/auth/request_otp`

**Purpose**: Start mobile sign-in for a registered field user.

**Request**:
```json
{
  "mobile": "9876543210"
}
```

**Response**:
- Success returns confirmation and may include auto-fill OTP details when current backend rules allow it.
- Failure returns a clear error for missing/unregistered mobile or SMS/config problems.

### `POST /api/auth/login`

**Purpose**: Exchange mobile number + OTP for a bearer token.

**Request**:
```json
{
  "mobile": "9876543210",
  "otp_input": "1234"
}
```

**Response**:
```json
{
  "user_id": 15,
  "user_name": "Patwari User",
  "login": "patwari@example.com",
  "mobile": "9876543210",
  "roles": [],
  "token": "jwt-token"
}
```

**Rules**:
- App must store `token` and send `Authorization: Bearer <token>` on protected endpoints.
- Expired/invalid token must redirect the app back to sign-in.

## 2. Survey CRUD Baseline

### `POST /api/bhukhadan/survey`

**Purpose**: Create a new survey using the current working mobile field set plus Area.

**Required contract behavior**:
- Existing working survey payload fields remain accepted.
- `area_id` is supported in create payloads.
- Payload must allow Khasra-prefilled values plus user-entered completion data.

### `GET /api/bhukhadan/survey`

**Purpose**: List surveys visible to the signed-in user.

**Query/filter behavior**:
- Existing list behavior stays intact.
- Khasra query (`q`) continues to work for search/prefill discovery flows.
- Returned summary rows should include enough context for app list and Khasra-search continuation.

### `GET /api/bhukhadan/survey/detail`
### `GET /api/bhukhadan/survey/<survey_id>`

**Purpose**: Fetch full survey detail for edit/view/prefill.

**Required contract behavior**:
- Full response must include all mobile-capture fields per [survey-field-parity.md](./survey-field-parity.md).
- `area_id` / `area_name` must be present in detail/summary responses (currently a known gap).
- `mb_*` declaration fields must be readable when set.

### `PATCH /api/bhukhadan/survey/<survey_id>`

**Purpose**: Update editable survey fields from the app.

**Required contract behavior**:
- Existing mobile baseline fields remain writable where business rules already allow updates.
- `area_id` updates are supported.
- Validation rejects invalid Project/Area/Village combinations.

## 3. Project → Area → Village Master Data

The app needs authenticated master-data lookups to drive dropdowns.

### Project dropdown

**Route**: `GET /api/bhukhadan/projects?department_id={optional}`

**Purpose**: Load projects available to the signed-in user under current access rules.

**Expected row shape**:
```json
{
  "id": 7,
  "name": "Project Name",
  "code": "PRJ-01"
}
```

### Area dropdown

**Route**: `GET /api/bhukhadan/areas?project_id={required}`

**Purpose**: After Project selection, load active Areas linked to that project’s villages.

**Expected row shape**:
```json
{
  "id": 3,
  "name": "Area North",
  "dropdown_label": "Area North",
  "village_count": 4
}
```

**Rules**:
- Only Areas linked through project villages are returned.
- Inactive Areas are excluded.
- Empty list is valid and must be surfaced clearly in the app.

### Village dropdown

**Route**: `GET /api/bhukhadan/villages?project_id={required}&area_id={required}`

**Purpose**: After Area selection, load villages for the selected Project + Area combination.

**Expected row shape**:
```json
{
  "id": 11,
  "name": "Village Name",
  "village_code": "VG-11",
  "display_code": "VG-11",
  "dropdown_label": "[VG-11] Village Name"
}
```

**Rules**:
- Village must remain disabled in the app until Area is selected.
- Only villages linked to both the selected project and the selected area are returned.
- Villages without `area_id` are not eligible for this mobile flow.

## 4. Khasra Prefill Contract

**Purpose**: When the user searches by Khasra, existing survey/search responses should provide values the app can immediately prefill.

**Rules**:
- The existing survey API field set is the canonical baseline for prefill.
- Prefill may be partial.
- App must preserve returned values and keep remaining editable fields open for user entry or correction.
- Prefill does not bypass save-time validation.

## 5. Parity Expectations

- See [survey-field-parity.md](./survey-field-parity.md) for the full `survey.py` ↔ API ↔ Flutter matrix.
- Flutter survey screens must mirror backend form sections (project/location, land, crop, house/infra, remarks/GPS, landowners, house owners, document checklist, trees, photos).
- Any matrix row marked **Gap** must be closed before release.
- Award/objection desk sections remain backend-only.

## 6. Validation Checklist

1. Sign in with OTP and obtain bearer token.
2. Load project choices for the signed-in user.
3. Select a project and load Areas.
4. Select an Area and verify Village becomes enabled.
5. Load villages filtered by selected Project + Area.
6. Search by Khasra and verify returned fields prefill the form.
7. Complete remaining editable fields and create survey successfully.
8. Reopen detail and verify Area plus prefilled/user-entered values are preserved.
9. Update an editable survey and verify invalid access/token cases fail safely.
