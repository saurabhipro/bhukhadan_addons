# BhuKhadan API tests (Playwright)

API-only Playwright suite that exercises every mobile REST endpoint in `bhukhadan_core`.

## Endpoints covered

| Method | Path | Spec |
|--------|------|------|
| POST | `/api/auth/request_otp` | `tests/auth.spec.ts` |
| POST | `/api/auth/login` | `tests/auth.spec.ts` |
| POST | `/api/auth/register` | `tests/auth.spec.ts` (negative) |
| GET | `/api/bhukhadan/projects` | `tests/masters.spec.ts` |
| GET | `/api/bhukhadan/areas` | `tests/masters.spec.ts` |
| GET | `/api/bhukhadan/villages` | `tests/masters.spec.ts` |
| GET | `/api/bhukhadan/survey` | `tests/surveys.spec.ts` |
| POST | `/api/bhukhadan/survey` | `tests/surveys.spec.ts` |
| GET | `/api/bhukhadan/survey/detail` | `tests/surveys.spec.ts` |
| GET | `/api/bhukhadan/survey/:id` | `tests/surveys.spec.ts` |
| PATCH | `/api/bhukhadan/survey/:id` | `tests/surveys.spec.ts` |
| POST | `/api/bhukhadan/survey/:id/owners` | `tests/surveys.spec.ts` |

## Prerequisites

1. Odoo running with `bhukhadan_core` upgraded
2. A registered mobile user (Patwari recommended so OTP is returned in `request_otp`)
3. At least one project with villages mapped to an **Area** (for create/patch flow)
4. Node.js 18+ with npm

## Setup

```bash
cd /opt/odoo18/custom_addons/bhukhadan_addons/bhukhadan_test
cp .env.example .env
# edit .env — set BHUKHADAN_BASE_URL and BHUKHADAN_TEST_MOBILE
npm install
```

No browser install is required (API `request` fixture only).

## Run

```bash
npm test                 # all API tests
npm run test:auth        # auth only
npm run test:masters     # projects / areas / villages
npm run test:surveys     # survey CRUD
npm run test:report      # HTML report
```

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `BHUKHADAN_BASE_URL` | yes | Odoo origin, e.g. `http://localhost:8069` |
| `BHUKHADAN_TEST_MOBILE` | yes | Registered user mobile |
| `BHUKHADAN_TEST_OTP` | no | Defaults to OTP from `request_otp.details` or `1234` |
| `BHUKHADAN_TEST_DEPARTMENT_ID` | no | Fallback if project payload has no `department_id` |
| `BHUKHADAN_SKIP_MUTATIONS` | no | Set `1` to skip create/update/owners tests |

## Notes

- Auth uses the same OTP flow as `bhukhadan_app`.
- Mutation tests create a temporary survey with khasra `PW-TEST-<timestamp>`.
- Endpoints referenced by the Flutter app but not yet implemented in core (trees, land-types, S3, PDF, dashboard) are intentionally omitted until those routes exist.
