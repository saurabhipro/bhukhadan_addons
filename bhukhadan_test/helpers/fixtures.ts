import { test as base, expect } from '@playwright/test';
import { AuthSession, loginWithOtp } from '../helpers/auth';

type Fixtures = {
  /** Authenticated mobile session (OTP login). Cached for the process. */
  auth: AuthSession;
};

let cachedAuth: AuthSession | null = null;

export const test = base.extend<Fixtures>({
  auth: async ({ request }, use) => {
    if (!cachedAuth) {
      cachedAuth = await loginWithOtp(request);
    }
    expect(cachedAuth.token).toBeTruthy();
    await use(cachedAuth);
  },
});

export { expect };
