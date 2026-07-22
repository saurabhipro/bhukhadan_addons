import { test, expect } from '@playwright/test';
import { Endpoints, expectFail, expectOk } from '../helpers/api';
import { authedPost, loginWithOtp } from '../helpers/auth';

/**
 * Screenshot audit:
 * - POST /api/bhukhadan/audit/screenshot (Bearer JWT)
 */
test.describe('Screenshot Audit API', () => {
  test('POST without token is rejected', async ({ request }) => {
    const res = await request.post(Endpoints.screenshotAudit, {
      data: { screen_name: 'Test', platform: 'android' },
    });
    // check_permission raises AccessError → typically 403 from Odoo HTTP
    await expectFail(res, [401, 403, 500]);
  });

  test('POST with bearer token creates audit event', async ({ request }) => {
    const session = await loginWithOtp(request);
    const res = await authedPost(request, Endpoints.screenshotAudit, session.token, {
      screen_name: 'Playwright Smoke',
      platform: 'android',
      device_info: 'playwright-test',
    });
    const body = await expectOk(res, { status: 201 });
    expect(body.message).toMatch(/logged/i);
    const data = body.data as Record<string, unknown>;
    expect(Number(data.id)).toBeGreaterThan(0);
    expect(Number(data.user_id)).toBe(session.userId);
    expect(data.ip_address).toBeTruthy();
    expect(data.event_time).toBeTruthy();
  });
});
