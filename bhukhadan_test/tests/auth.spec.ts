import { test, expect } from '@playwright/test';
import { Endpoints, expectFail, expectOk, parseJson } from '../helpers/api';
import { loginWithOtp, testCredentials } from '../helpers/auth';

/**
 * Auth endpoints:
 * - POST /api/auth/request_otp
 * - POST /api/auth/login
 * - POST /api/auth/register (negative / shape only)
 */
test.describe('Auth API', () => {
  test('POST /api/auth/request_otp rejects missing mobile', async ({ request }) => {
    const res = await request.post(Endpoints.requestOtp, { data: {} });
    await expectFail(res, 400);
  });

  test('POST /api/auth/request_otp rejects unregistered mobile', async ({ request }) => {
    const res = await request.post(Endpoints.requestOtp, {
      data: { mobile: '0000000000' },
    });
    const body = await expectFail(res, 400);
    expect(String(body.error || '')).toMatch(/not register/i);
  });

  test('POST /api/auth/request_otp succeeds for registered mobile', async ({ request }) => {
    const { mobile } = testCredentials();
    const res = await request.post(Endpoints.requestOtp, { data: { mobile } });
    const body = await parseJson(res);
    expect(res.status(), JSON.stringify(body)).toBe(200);
    expect(body.message || body.details).toBeTruthy();
  });

  test('POST /api/auth/login rejects missing fields', async ({ request }) => {
    const res = await request.post(Endpoints.login, { data: { mobile: '9876543210' } });
    await expectFail(res, 400);
  });

  test('POST /api/auth/login rejects invalid OTP', async ({ request }) => {
    const { mobile } = testCredentials();
    await request.post(Endpoints.requestOtp, { data: { mobile } });
    const res = await request.post(Endpoints.login, {
      data: { mobile, otp_input: '0000' },
    });
    // Invalid OTP → 400; static OTP mismatch may also 400
    const body = await parseJson(res);
    expect([400, 403]).toContain(res.status());
    expect(body.error || body.message).toBeTruthy();
  });

  test('OTP login returns bearer token', async ({ request }) => {
    const session = await loginWithOtp(request);
    expect(session.token.length).toBeGreaterThan(20);
    expect(session.userId).toBeGreaterThan(0);
  });

  test('POST /api/auth/register rejects incomplete payload', async ({ request }) => {
    const res = await request.post(Endpoints.register, { data: {} });
    // Implementation may return 400/403/500 depending on validation
    expect(res.status()).toBeGreaterThanOrEqual(400);
  });
});
