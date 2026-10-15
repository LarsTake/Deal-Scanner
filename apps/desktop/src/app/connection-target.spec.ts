import { describe, expect, it } from 'vitest';
import { defaultApiUrl } from './connection-target';

describe('defaultApiUrl', () => {
  it('uses the server origin for a remotely opened web interface', () => {
    expect(defaultApiUrl(new URL('https://scanner.example.test/listings'), false))
      .toBe('https://scanner.example.test');
  });
  it('keeps the development API separate', () => {
    expect(defaultApiUrl(new URL('http://localhost:4200'), false)).toBe('http://127.0.0.1:8000');
  });
  it('keeps native defaults local until explicitly configured', () => {
    expect(defaultApiUrl(new URL('http://tauri.localhost'), true)).toBe('http://127.0.0.1:8000');
  });
});
