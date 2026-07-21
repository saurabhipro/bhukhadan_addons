import { APIRequestContext, expect } from '@playwright/test';
import { Endpoints, authHeader, expectOk, parseJson } from './api';

export type AuthSession = {
  token: string;
  userId: number;
  mobile: string;
  userName?: string;
};

function env(name: string, fallback = ''): string {
  return (process.env[name] || fallback).trim();
}

export function testCredentials() {
  const mobile = env('BHUKHADAN_TEST_MOBILE');
  const otp = env('BHUKHADAN_TEST_OTP');
  if (!mobile) {
    throw new Error(
      'Set BHUKHADAN_TEST_MOBILE in bhukhadan_test/.env (see .env.example)',
    );
  }
  return { mobile, otp };
}

/**
 * OTP login flow used by the Flutter app:
 * 1) POST /api/auth/request_otp
 * 2) POST /api/auth/login with otp_input
 */
export async function loginWithOtp(request: APIRequestContext): Promise<AuthSession> {
  const { mobile, otp: envOtp } = testCredentials();

  const otpRes = await request.post(Endpoints.requestOtp, {
    data: { mobile },
  });
  const otpBody = await parseJson(otpRes);
  if (otpRes.status() !== 200) {
    throw new Error(
      `OTP request failed for mobile=${mobile} status=${otpRes.status()} ` +
        `body=${JSON.stringify(otpBody)}. ` +
        `Register this mobile on an Odoo user (res.users.mobile) or update BHUKHADAN_TEST_MOBILE in .env`,
    );
  }

  const otpFromApi =
    (otpBody.details as string | undefined) ||
    (otpBody.otp as string | undefined) ||
    '';
  // Prefer OTP returned by request_otp (Patwari auto-fill / static OTP in response).
  // BHUKHADAN_TEST_OTP is only a fallback when the API does not echo the code.
  const otp = otpFromApi || envOtp;
  expect(otp, 'No OTP available — enable static OTP or set BHUKHADAN_TEST_OTP').toBeTruthy();

  const loginRes = await request.post(Endpoints.login, {
    data: { mobile, otp_input: otp },
  });
  const loginBody = await parseJson(loginRes);
  if (loginRes.status() !== 200) {
    throw new Error(
      `Login failed status=${loginRes.status()} body=${JSON.stringify(loginBody)}. ` +
        `If using static OTP, match BHUKHADAN_TEST_OTP to Settings Master; ` +
        `otherwise rely on request_otp.details (now preferred automatically).`,
    );
  }
  expect(loginBody.token, JSON.stringify(loginBody)).toBeTruthy();

  return {
    token: String(loginBody.token),
    userId: Number(loginBody.user_id),
    mobile: String(loginBody.mobile || mobile),
    userName: loginBody.user_name ? String(loginBody.user_name) : undefined,
  };
}

export async function authedGet(
  request: APIRequestContext,
  path: string,
  token: string,
  params?: Record<string, string | number | undefined>,
) {
  const qs = params
    ? '?' +
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join('&')
    : '';
  return request.get(`${path}${qs}`, { headers: authHeader(token) });
}

export async function authedPost(
  request: APIRequestContext,
  path: string,
  token: string,
  data: unknown,
) {
  return request.post(path, { headers: authHeader(token), data });
}

export async function authedPatch(
  request: APIRequestContext,
  path: string,
  token: string,
  data: unknown,
) {
  return request.patch(path, { headers: authHeader(token), data });
}

/** Resolve Project → Area → Village cascade for mutation tests. */
export async function resolveLocationCascade(request: APIRequestContext, token: string) {
  const projectsBody = await expectOk(await authedGet(request, Endpoints.projects, token));
  const projects = (projectsBody.data as Array<Record<string, unknown>>) || [];
  expect(projects.length, 'No projects for test user').toBeGreaterThan(0);

  for (const p of projects) {
    const areasBody = await expectOk(
      await authedGet(request, Endpoints.areas, token, { project_id: Number(p.id) }),
    );
    const areaList = (areasBody.data as Array<Record<string, unknown>>) || [];
    for (const a of areaList) {
      const villagesBody = await expectOk(
        await authedGet(request, Endpoints.villages, token, {
          project_id: Number(p.id),
          area_id: Number(a.id),
        }),
      );
      const villageList = (villagesBody.data as Array<Record<string, unknown>>) || [];
      if (!villageList.length) continue;

      const departmentId =
        Number(p.department_id) ||
        Number(process.env.BHUKHADAN_TEST_DEPARTMENT_ID) ||
        0;

      return {
        projectId: Number(p.id),
        departmentId,
        areaId: Number(a.id),
        villageId: Number(villageList[0].id),
        project: p,
        area: a,
        village: villageList[0],
      };
    }
  }

  throw new Error('No project with Area→Village mapping for test user');
}
