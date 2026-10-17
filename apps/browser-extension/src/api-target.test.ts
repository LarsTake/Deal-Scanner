import { describe, expect, it } from 'vitest';

import { validateApiTarget } from './api-target';

describe('validateApiTarget', () => {
  it('accepts HTTPS and loopback HTTP while producing a port-independent match pattern', () => {
    expect(validateApiTarget('http://127.0.0.1:54321/')).toEqual({
      apiUrl: 'http://127.0.0.1:54321',
      permissionPattern: 'http://127.0.0.1/*',
    });
    expect(validateApiTarget('https://scanner.example')).toEqual({
      apiUrl: 'https://scanner.example',
      permissionPattern: 'https://scanner.example/*',
    });
  });

  it('rejects insecure remote targets and embedded credentials', () => {
    expect(() => validateApiTarget('http://scanner.example')).toThrow(/HTTPS/);
    expect(() => validateApiTarget('https://user:secret@scanner.example')).toThrow(/Zugangsdaten/);
  });

  it('supports a local server on LAN or WLAN without granting every HTTP host', () => {
    expect(validateApiTarget('http://192.168.1.10:8088')).toEqual({
      apiUrl: 'http://192.168.1.10:8088', permissionPattern: 'http://192.168.1.10/*',
    });
    expect(() => validateApiTarget('http://8.8.8.8')).toThrow();
  });
});
