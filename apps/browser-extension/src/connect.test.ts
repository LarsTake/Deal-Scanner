import { afterEach, describe, expect, it, vi } from 'vitest';
import { connectPreparedScanner, prepareActiveScanner } from './connect';

describe('account handoff from the signed-in dashboard', () => {
  afterEach(() => vi.unstubAllGlobals());
  function setup(granted = true, returnedApi = 'https://scanner.example') {
    const executeScript = vi.fn()
      .mockResolvedValueOnce([{ result: 'https://scanner.example' }])
      .mockResolvedValueOnce([{ result: { apiUrl: returnedApi, token: 'fixture-device-token' } }]);
    const save = vi.fn(async () => undefined);
    vi.stubGlobal('chrome', {
      tabs: { query: vi.fn(async () => [{ id: 1 }]) }, scripting: { executeScript },
      permissions: { request: vi.fn(async () => granted) },
      storage: { sync: { set: save }, local: { set: save } },
    });
    return { executeScript, save };
  }

  it('stores the API and scoped device token without requesting a password', async () => {
    const { save } = setup();
    await connectPreparedScanner(await prepareActiveScanner());
    expect(save).toHaveBeenCalledWith({ apiUrl: 'https://scanner.example', tokenType: 'pairing' });
    expect(save).toHaveBeenCalledWith({ token: 'fixture-device-token' });
  });

  it('does not mint or store a token if host permission is denied', async () => {
    const { executeScript, save } = setup(false);
    const prepared = await prepareActiveScanner();
    await expect(connectPreparedScanner(prepared)).rejects.toThrow('abgelehnt');
    expect(executeScript).toHaveBeenCalledTimes(1);
    expect(save).not.toHaveBeenCalled();
  });

  it('rejects a changed API address during the handoff', async () => {
    const { save } = setup(true, 'https://other.example');
    const prepared = await prepareActiveScanner();
    await expect(connectPreparedScanner(prepared)).rejects.toThrow('unvollständig');
    expect(save).not.toHaveBeenCalled();
  });
});
