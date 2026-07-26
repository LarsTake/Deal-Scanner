import { TestBed } from '@angular/core/testing';
import {
  type ActivatedRouteSnapshot,
  Router,
  type RouterStateSnapshot,
} from '@angular/router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { requireAuthentication } from './auth.guard';
import { AuthService } from './auth.service';

describe('requireAuthentication', () => {
  const auth = {
    waitUntilInitialized: vi.fn<() => Promise<void>>(),
    configured: vi.fn<() => boolean>(),
    getAccessToken: vi.fn<() => Promise<string | null>>(),
  };
  const router = {
    createUrlTree: vi.fn((commands: string[], extras?: unknown) => ({ commands, extras })),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    auth.waitUntilInitialized.mockResolvedValue();
    auth.configured.mockReturnValue(true);
    auth.getAccessToken.mockResolvedValue(null);
    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: auth },
        { provide: Router, useValue: router },
      ],
    });
  });

  async function runGuard(url: string): Promise<unknown> {
    return TestBed.runInInjectionContext(() =>
      requireAuthentication(
        {} as ActivatedRouteSnapshot,
        { url } as RouterStateSnapshot,
      ),
    );
  }

  it('allows a protected route after a session token was restored', async () => {
    auth.getAccessToken.mockResolvedValue('access-token');

    await expect(runGuard('/listings')).resolves.toBe(true);
    expect(auth.waitUntilInitialized).toHaveBeenCalledOnce();
  });

  it('redirects signed-out users to login and preserves the requested route', async () => {
    await expect(runGuard('/listings')).resolves.toEqual({
      commands: ['/login'],
      extras: { queryParams: { returnUrl: '/listings' } },
    });
  });

  it('redirects to settings when Supabase is not configured', async () => {
    auth.configured.mockReturnValue(false);

    await expect(runGuard('/')).resolves.toEqual({
      commands: ['/settings'],
      extras: undefined,
    });
    expect(auth.getAccessToken).not.toHaveBeenCalled();
  });
});
