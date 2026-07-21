import { APIRequestContext, expect } from '@playwright/test';

export type Json = Record<string, unknown>;

export function authHeader(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

export async function parseJson(response: Awaited<ReturnType<APIRequestContext['get']>>): Promise<Json> {
  const text = await response.text();
  try {
    return JSON.parse(text) as Json;
  } catch {
    throw new Error(`Expected JSON, got status=${response.status()} body=${text.slice(0, 500)}`);
  }
}

export async function expectOk(
  response: Awaited<ReturnType<APIRequestContext['get']>>,
  opts: { status?: number | number[]; success?: boolean } = {},
): Promise<Json> {
  const allowed = opts.status === undefined
    ? [200, 201]
    : Array.isArray(opts.status)
      ? opts.status
      : [opts.status];
  const body = await parseJson(response);
  expect(
    allowed,
    `Unexpected status ${response.status()} body=${JSON.stringify(body)}`,
  ).toContain(response.status());
  if (opts.success !== false && body.success !== undefined) {
    expect(body.success, JSON.stringify(body)).toBe(true);
  }
  return body;
}

export async function expectFail(
  response: Awaited<ReturnType<APIRequestContext['get']>>,
  status: number | number[],
): Promise<Json> {
  const allowed = Array.isArray(status) ? status : [status];
  const body = await parseJson(response);
  expect(
    allowed,
    `Expected failure status ${allowed.join('|')}, got ${response.status()} body=${JSON.stringify(body)}`,
  ).toContain(response.status());
  return body;
}

/** Endpoints implemented under bhukhadan_core controllers/api */
export const Endpoints = {
  requestOtp: '/api/auth/request_otp',
  login: '/api/auth/login',
  register: '/api/auth/register',
  projects: '/api/bhukhadan/projects',
  areas: '/api/bhukhadan/areas',
  villages: '/api/bhukhadan/villages',
  surveys: '/api/bhukhadan/survey',
  surveyDetail: '/api/bhukhadan/survey/detail',
  surveyById: (id: number | string) => `/api/bhukhadan/survey/${id}`,
  surveyOwners: (id: number | string) => `/api/bhukhadan/survey/${id}/owners`,
} as const;
