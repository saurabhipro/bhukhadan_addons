import { Endpoints, authHeader, expectFail, expectOk, parseJson } from '../helpers/api';
import { authedGet, authedPatch, authedPost, resolveLocationCascade } from '../helpers/auth';
import { expect, test } from '../helpers/fixtures';

/**
 * Survey CRUD + owners:
 * GET/POST /api/bhukhadan/survey
 * GET /api/bhukhadan/survey/detail
 * GET/PATCH /api/bhukhadan/survey/:id
 * POST /api/bhukhadan/survey/:id/owners
 */
test.describe('Survey API', () => {
  test('GET /api/bhukhadan/survey requires Authorization', async ({ request }) => {
    const res = await request.get(Endpoints.surveys);
    expect([401, 403, 500]).toContain(res.status());
  });

  test('GET /api/bhukhadan/survey lists surveys for user', async ({ request, auth }) => {
    const body = await expectOk(await authedGet(request, Endpoints.surveys, auth.token));
    expect(body.data !== undefined || body.surveys !== undefined || Array.isArray(body)).toBeTruthy();
  });

  test('GET /api/bhukhadan/survey supports khasra search q=', async ({ request, auth }) => {
    const body = await expectOk(
      await authedGet(request, Endpoints.surveys, auth.token, { q: '1' }),
    );
    expect(body.success).toBe(true);
  });

  test('GET /api/bhukhadan/survey/:id returns 404 for missing id', async ({ request, auth }) => {
    const res = await request.get(Endpoints.surveyById(999999999), {
      headers: authHeader(auth.token),
    });
    await expectFail(res, [404, 403, 400]);
  });

  test('POST /api/bhukhadan/survey rejects incomplete payload', async ({ request, auth }) => {
    const res = await authedPost(request, Endpoints.surveys, auth.token, {
      khasra_number: 'TEST-INCOMPLETE',
    });
    await expectFail(res, 400);
  });

  test('create → get → patch → owners survey flow', async ({ request, auth }) => {
    test.skip(process.env.BHUKHADAN_SKIP_MUTATIONS === '1', 'Mutations skipped via env');

    const loc = await resolveLocationCascade(request, auth.token);
    test.skip(!loc.departmentId, 'Project has no department_id — set BHUKHADAN_TEST_DEPARTMENT_ID');

    const khasra = `PW-TEST-${Date.now()}`;
    const createPayload = {
      project_id: loc.projectId,
      department_id: loc.departmentId,
      area_id: loc.areaId,
      village_id: loc.villageId,
      khasra_number: khasra,
      total_area: 1.5,
      acquired_area: 1.0,
      survey_type: 'land',
      landowners: [
        {
          name: 'Playwright Test Owner',
          father_name: 'Test Father',
          phone: '9999999999',
        },
      ],
      mb_decl_no_claim_pending: true,
      mb_decl_documents_received: true,
      mb_decl_gps_photo_video: false,
    };

    const createRes = await authedPost(request, Endpoints.surveys, auth.token, createPayload);
    const createBody = await expectOk(createRes, { status: [200, 201] });
    const created = (createBody.data || createBody) as Record<string, unknown>;
    const surveyId = Number(created.id || created.survey_id);
    expect(surveyId).toBeGreaterThan(0);
    expect(created.area_id === loc.areaId || Number(created.area_id) === loc.areaId).toBeTruthy();

    // GET by id
    const detailBody = await expectOk(
      await authedGet(request, Endpoints.surveyById(surveyId), auth.token),
    );
    const detail = (detailBody.data || detailBody) as Record<string, unknown>;
    expect(String(detail.khasra_number || '')).toContain('PW-TEST');
    expect(detail).toHaveProperty('area_id');

    // GET detail query variant
    const detailQs = await expectOk(
      await authedGet(request, Endpoints.surveyDetail, auth.token, { survey_id: surveyId }),
    );
    expect(detailQs.success).toBe(true);

    // PATCH remarks + mb field
    const patchBody = await expectOk(
      await authedPatch(request, Endpoints.surveyById(surveyId), auth.token, {
        remarks: 'Updated by Playwright',
        mb_decl_gps_photo_video: true,
      }),
    );
    const patched = (patchBody.data || patchBody) as Record<string, unknown>;
    expect(String(patched.remarks || '')).toMatch(/Playwright/);

    // POST owners append
    const ownersRes = await authedPost(request, Endpoints.surveyOwners(surveyId), auth.token, {
      landowners: [{ name: 'Extra Owner', phone: '8888888888' }],
    });
    const ownersBody = await parseJson(ownersRes);
    expect([200, 201]).toContain(ownersRes.status());
    expect(ownersBody.success !== false).toBeTruthy();
  });

  test('PATCH /api/bhukhadan/survey/:id rejects invalid location combo', async ({
    request,
    auth,
  }) => {
    test.skip(process.env.BHUKHADAN_SKIP_MUTATIONS === '1', 'Mutations skipped via env');

    const listBody = await expectOk(await authedGet(request, Endpoints.surveys, auth.token));
    const rows =
      (listBody.data as Array<Record<string, unknown>>) ||
      (listBody.surveys as Array<Record<string, unknown>>) ||
      [];
    test.skip(!rows.length, 'No surveys to patch');

    const surveyId = Number(rows[0].id);
    const res = await authedPatch(request, Endpoints.surveyById(surveyId), auth.token, {
      area_id: 999999999,
    });
    // Validation or access / not editable
    expect([400, 403, 404]).toContain(res.status());
  });
});
