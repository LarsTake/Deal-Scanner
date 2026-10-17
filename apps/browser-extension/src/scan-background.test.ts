import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { handleScanMessage } from './scan-background';

const sender = { tab: { id: 42, url: 'https://www.kleinanzeigen.de/s-computer/k0' } } as chrome.runtime.MessageSender;
const options = { maxPages: 2, maxListings: 10, delaySeconds: 3 };
let stored: Record<string, unknown>;

describe('scan ownership and stop handling', () => {
  beforeEach(() => {
    stored = {};
    vi.stubGlobal('chrome', {
      storage: {
        session: { get: vi.fn(async () => stored), set: vi.fn(async (value) => Object.assign(stored, value)) },
        sync: { get: vi.fn(async () => ({ apiUrl: 'https://scanner.example' })) },
        local: { get: vi.fn(async () => ({ token: 'fixture-device-token' })) },
      },
      tabs: { sendMessage: vi.fn(async () => ({})) },
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it('does not resurrect a stopped run when an in-flight page sends progress', async () => {
    const state = await handleScanMessage({ type: 'SCAN_START', options }, sender);
    await handleScanMessage({ type: 'SCAN_STOP' }, sender);
    const result = await handleScanMessage({ type: 'SCAN_PROGRESS', state: state as never }, sender);
    expect(result).toMatchObject({ status: 'stopped' });
  });

  it('rejects overlapping runs and ignores progress belonging to an earlier run', async () => {
    const state = await handleScanMessage({ type: 'SCAN_START', options }, sender);
    await expect(handleScanMessage({ type: 'SCAN_START', options }, sender)).rejects.toThrow('bereits');
    const result = await handleScanMessage({ type: 'SCAN_PROGRESS', state: { ...(state as object), id: 'old-run' } as never }, sender);
    expect(result).toEqual(state);
  });
});
