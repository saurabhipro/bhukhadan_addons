import { Endpoints, authHeader, expectFail, expectOk, parseJson } from '../helpers/api';
import { authedDelete, authedPost } from '../helpers/auth';
import { expect, test } from '../helpers/fixtures';

/**
 * Screenshot audit API:
 * POST   /api/bhukhadan/audit/screenshot
 * DELETE /api/bhukhadan/audit/screenshot/:id
 *
 * Contract: specs/003-screenshot-tracker/contracts/screenshot-audit-api.md
 *
 * Creating tests always DELETE the row afterward so the admin log stays clean.
 */
test.describe('Screenshot Audit API', () => {
  const createdIds: number[] = [];

  async function createEvent(
    request: Parameters<typeof authedPost>[0],
    token: string,
    data: Record<string, unknown>,
  ) {
    const res = await authedPost(request, Endpoints.screenshotAudit, token, data);
    const body = await expectOk(res, { status: 201 });
    const id = Number((body.data as Record<string, unknown>).id);
    expect(id).toBeGreaterThan(0);
    createdIds.push(id);
    return { body, id, data: body.data as Record<string, unknown> };
  }

  async function deleteEvent(
    request: Parameters<typeof authedDelete>[0],
    token: string,
    id: number,
  ) {
    const res = await authedDelete(request, Endpoints.screenshotAuditById(id), token);
    await expectOk(res, { status: 200 });
    const idx = createdIds.indexOf(id);
    if (idx >= 0) createdIds.splice(idx, 1);
  }

  test.afterEach(async ({ request, auth }) => {
    // Safety net: remove any ids left if a test forgot explicit cleanup
    const leftover = [...createdIds];
    createdIds.length = 0;
    for (const id of leftover) {
      const res = await authedDelete(request, Endpoints.screenshotAuditById(id), auth.token);
      // 200 deleted, 404 already gone — both fine for cleanup
      expect([200, 404]).toContain(res.status());
    }
  });

  test('POST without Authorization is rejected', async ({ request }) => {
    const res = await request.post(Endpoints.screenshotAudit, {
      data: { screen_name: 'Unauthed', platform: 'android' },
    });
    expect([401, 403, 500]).toContain(res.status());
  });

  test('POST with invalid bearer token is rejected', async ({ request }) => {
    const res = await request.post(Endpoints.screenshotAudit, {
      headers: authHeader('not-a-valid-jwt'),
      data: { screen_name: 'BadToken', platform: 'ios' },
    });
    expect([401, 403, 500]).toContain(res.status());
  });

  test('POST creates then DELETE removes audit event (no leftover)', async ({ request, auth }) => {
    const { id, data } = await createEvent(request, auth.token, {
      screen_name: 'Playwright Smoke',
      platform: 'android',
      device_info: 'playwright-test',
      notes: 'api smoke',
    });
    expect(Number(data.user_id)).toBe(auth.userId);
    expect(String(data.ip_address || '').length).toBeGreaterThan(0);
    expect(data.event_time).toBeTruthy();

    await deleteEvent(request, auth.token, id);

    // Second delete → 404
    const again = await authedDelete(request, Endpoints.screenshotAuditById(id), auth.token);
    await expectFail(again, 404);
  });

  test('POST accepts ios platform; cleanup via DELETE', async ({ request, auth }) => {
    const { id } = await createEvent(request, auth.token, { platform: 'ios' });
    await deleteEvent(request, auth.token, id);
  });

  test('POST coerces unknown platform; cleanup via DELETE', async ({ request, auth }) => {
    const { id } = await createEvent(request, auth.token, {
      screen_name: 'Unknown Platform Screen',
      platform: 'not-a-real-os',
      device_info: 'playwright',
    });
    await deleteEvent(request, auth.token, id);
  });

  test('POST ignores invalid survey_id; cleanup via DELETE', async ({ request, auth }) => {
    const { id } = await createEvent(request, auth.token, {
      screen_name: 'Survey Details',
      platform: 'android',
      survey_id: 999999999,
    });
    await deleteEvent(request, auth.token, id);
  });

  test('POST records X-Forwarded-For; cleanup via DELETE', async ({ request, auth }) => {
    const res = await request.post(Endpoints.screenshotAudit, {
      headers: {
        ...authHeader(auth.token),
        'X-Forwarded-For': '203.0.113.77, 10.0.0.1',
      },
      data: {
        screen_name: 'IP Header Test',
        platform: 'android',
        device_info: 'playwright-xff',
      },
    });
    const body = await expectOk(res, { status: 201 });
    const data = body.data as Record<string, unknown>;
    const id = Number(data.id);
    createdIds.push(id);
    expect(String(data.ip_address)).toBe('203.0.113.77');
    await deleteEvent(request, auth.token, id);
  });

  test('POST with empty body succeeds; cleanup via DELETE', async ({ request, auth }) => {
    const { id, data } = await createEvent(request, auth.token, {});
    expect(Number(data.user_id)).toBe(auth.userId);
    await deleteEvent(request, auth.token, id);
  });

  test('DELETE without token is rejected', async ({ request, auth }) => {
    const { id } = await createEvent(request, auth.token, {
      screen_name: 'Delete Auth Check',
      platform: 'android',
    });
    const res = await request.delete(Endpoints.screenshotAuditById(id));
    expect([401, 403, 500]).toContain(res.status());
    // still owned by auth user — cleanup
    await deleteEvent(request, auth.token, id);
  });

  test('DELETE unknown id returns 404', async ({ request, auth }) => {
    const res = await authedDelete(request, Endpoints.screenshotAuditById(999999999), auth.token);
    await expectFail(res, 404);
  });

  test('POST with invalid JSON body is not 201', async ({ request, auth }) => {
    const res = await request.post(Endpoints.screenshotAudit, {
      headers: {
        ...authHeader(auth.token),
        'Content-Type': 'application/json',
      },
      data: '{not-json',
    });
    const status = res.status();
    if (status === 400) {
      const body = await parseJson(res);
      expect(body.success).toBe(false);
    } else {
      expect(status).not.toBe(201);
    }
  });
});
