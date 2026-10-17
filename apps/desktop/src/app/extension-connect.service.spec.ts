import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiService } from './api.service';
import { AuthService } from './auth.service';
import { ExtensionConnectService } from './extension-connect.service';

describe('dashboard account connection for Chrome', () => {
  let service: ExtensionConnectService;
  const create = vi.fn();
  const userEmail = vi.fn();
  beforeEach(() => {
    localStorage.setItem('deal-scanner-api-url', 'https://scanner.example');
    create.mockReset().mockResolvedValue({ token: 'device-fixture' });
    userEmail.mockReturnValue('account@example.test');
    TestBed.configureTestingModule({ providers: [
      ExtensionConnectService,
      { provide: AuthService, useValue: { userEmail } },
      { provide: ApiService, useValue: { createExtensionConnection: create } },
    ] });
    service = TestBed.inject(ExtensionConnectService);
    service.start();
  });
  afterEach(() => { service.ngOnDestroy(); localStorage.clear(); vi.restoreAllMocks(); });
  function request(source: MessageEventSource | null = window) {
    window.dispatchEvent(new MessageEvent('message', { source, origin: location.origin,
      data: { type: 'DEAL_SCANNER_CONNECT', nonce: 'fixture-nonce' } }));
  }

  it('returns only a newly issued device token and API from the signed-in account', async () => {
    const reply = vi.spyOn(window, 'postMessage').mockImplementation(() => undefined);
    request();
    await vi.waitFor(() => expect(reply).toHaveBeenCalledWith({
      type: 'DEAL_SCANNER_CONNECTED', nonce: 'fixture-nonce', apiUrl: 'https://scanner.example', token: 'device-fixture',
    }, location.origin));
    expect(create).toHaveBeenCalledOnce();
  });

  it('does not mint a token for a signed-out user or a different frame', async () => {
    userEmail.mockReturnValue(null);
    const reply = vi.spyOn(window, 'postMessage').mockImplementation(() => undefined);
    request();
    await vi.waitFor(() => expect(reply).toHaveBeenCalledWith(expect.objectContaining({ error: expect.stringContaining('anmelden') }), location.origin));
    expect(create).not.toHaveBeenCalled();
    reply.mockClear();
    userEmail.mockReturnValue('account@example.test');
    request(null);
    expect(create).not.toHaveBeenCalled();
    expect(reply).not.toHaveBeenCalled();
  });
});
