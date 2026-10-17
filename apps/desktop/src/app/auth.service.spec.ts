import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { AuthService } from './auth.service';
import type { SecureTokenStore } from './secure-token.store';

describe('server auth bootstrap', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  it('loads the public connection without credentials from the configured server', async () => {
    localStorage.setItem('deal-scanner-api-url', 'http://scanner.test:8088/');
    const request = vi.fn(async () => new Response(JSON.stringify({
      authMode: 'supabase', supabaseUrl: 'https://project.example.test',
      supabasePublishableKey: 'sb_publishable_fixture',
    })));
    vi.stubGlobal('fetch', request);
    const service = new AuthService({} as SecureTokenStore);
    const configure = vi.spyOn(service, 'configure').mockImplementation(() => undefined);
    await service.initializeFromServer();
    expect(request).toHaveBeenCalledWith('http://scanner.test:8088/api/v1/client-config',
      expect.objectContaining({ credentials: 'omit', cache: 'no-store' }));
    expect(configure).toHaveBeenCalledWith('https://project.example.test', 'sb_publishable_fixture');
    expect(service.serverConfigured()).toBe(true);
  });

  it('does not block startup when the server is offline', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline'); }));
    const service = new AuthService({} as SecureTokenStore);
    await service.initializeFromServer();
    expect(service.serverConfigured()).toBe(false);
  });

  it('ignores incomplete server configuration', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ authMode: 'supabase' }))));
    const service = new AuthService({} as SecureTokenStore);
    const configure = vi.spyOn(service, 'configure');
    await service.initializeFromServer();
    expect(configure).not.toHaveBeenCalled();
  });
});
