import { describe, expect, it } from 'vitest';

import { readAuthRedirectError, resolvePasswordRecoveryRedirect } from './auth.service';

describe('password recovery URL handling', () => {
  it('returns the login route on the active browser origin', () => {
    expect(resolvePasswordRecoveryRedirect('http://127.0.0.1:4200', false)).toBe(
      'http://127.0.0.1:4200/login',
    );
    expect(resolvePasswordRecoveryRedirect('https://scanner.example', false)).toBe(
      'https://scanner.example/login',
    );
  });

  it('uses the local browser callback for the installed Tauri app', () => {
    expect(resolvePasswordRecoveryRedirect('http://tauri.localhost', true)).toBe(
      'http://127.0.0.1:4200/login',
    );
  });

  it('extracts Supabase errors from the redirect fragment', () => {
    expect(
      readAuthRedirectError(
        'http://127.0.0.1:4200/login#error=access_denied&error_description=Email+link+is+invalid',
      ),
    ).toBe('Email link is invalid');
  });
});
