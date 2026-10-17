import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { AuthService } from './auth.service';
import type { SecureTokenStore } from './secure-token.store';

const nativeInvoke = vi.hoisted(() => vi.fn());
vi.mock('@tauri-apps/api/core', () => ({ invoke: nativeInvoke }));

describe('server auth bootstrap', () => {
  beforeEach(() => { localStorage.clear(); nativeInvoke.mockReset(); });
  afterEach(() => {
    delete (window as unknown as Record<string, unknown>)['__TAURI_INTERNALS__'];
    vi.unstubAllGlobals();
  });

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

  it('explains local development mode without asking for Supabase keys', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ authMode: 'development' }))));
    const service = new AuthService({} as SecureTokenStore);
    await service.initializeFromServer();
    expect(service.configured()).toBe(false);
    expect(service.connectionMessage()).toContain('zentralen Scanner-Server');
  });

  it('distinguishes an outdated server from missing client credentials', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 404 })));
    const service = new AuthService({} as SecureTokenStore);
    await service.initializeFromServer();
    expect(service.connectionMessage()).toContain('Serverversion');
  });

  it('uses the saved WLAN connection in the desktop app instead of an old LAN address', async () => {
    Object.defineProperty(window, '__TAURI_INTERNALS__', { value: {}, configurable: true });
    localStorage.setItem('deal-scanner-server-addresses', JSON.stringify(['http://192.168.178.20:8088']));
    nativeInvoke.mockResolvedValue(['http://192.168.178.169:8088']);
    const request = vi.fn(async () => Response.json({
      authMode: 'supabase', supabaseUrl: 'https://project.example.test', supabasePublishableKey: 'sb_publishable_fixture',
    }));
    vi.stubGlobal('fetch', request);
    const service = new AuthService({} as SecureTokenStore);
    vi.spyOn(service, 'configure').mockImplementation(() => undefined);
    await service.initializeFromServer();
    expect(nativeInvoke).toHaveBeenCalledWith('server_connection');
    expect(request).toHaveBeenCalledExactlyOnceWith('http://192.168.178.169:8088/api/v1/client-config',
      expect.objectContaining({ credentials: 'omit' }));
    expect(localStorage.getItem('deal-scanner-api-url')).toBe('http://192.168.178.169:8088');
    expect(service.serverConfigured()).toBe(true);
  });
});
