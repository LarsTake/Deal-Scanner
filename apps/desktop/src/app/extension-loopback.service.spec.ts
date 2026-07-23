import { afterEach, describe, expect, it } from 'vitest';

import { resolveDevelopmentUserId } from './extension-loopback.service';

describe('resolveDevelopmentUserId', () => {
  afterEach(() => localStorage.removeItem('deal-scanner-development-user'));

  it('uses the same local default identity as the API client', () => {
    expect(resolveDevelopmentUserId()).toBe('00000000-0000-4000-8000-000000000001');
  });

  it('keeps an explicitly configured development identity', () => {
    localStorage.setItem(
      'deal-scanner-development-user',
      '00000000-0000-4000-8000-000000000099',
    );

    expect(resolveDevelopmentUserId()).toBe('00000000-0000-4000-8000-000000000099');
  });
});
