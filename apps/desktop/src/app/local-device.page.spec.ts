import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LocalDevicePage } from './local-device.page';

const invoke = vi.fn<(name: string, args?: Record<string, unknown>) => Promise<unknown>>();
let page: LocalDevicePage;

describe('local worker controls', () => {
  beforeEach(() => {
    page = new LocalDevicePage();
    invoke.mockReset();
    vi.spyOn(page as unknown as { invoke(name: string, args?: Record<string, unknown>): Promise<unknown> }, 'invoke')
      .mockImplementation((name, args) => invoke(name, args));
  });
  afterEach(() => vi.restoreAllMocks());

  it('persists text-only settings before starting and clears the password field', async () => {
    vi.mocked(invoke).mockResolvedValue({ running: true, legacyService: false, passwordSaved: true, config: {} });
    page.form.patchValue({ password: 'test-fixture', textModel: 'installed-model', images: false });
    await page.start();
    expect(invoke).toHaveBeenNthCalledWith(1, 'save_local_worker', expect.objectContaining({
      config: expect.objectContaining({ images: false, textModel: 'installed-model', passwordFile: '' }),
      password: 'test-fixture',
    }));
    expect(invoke).toHaveBeenNthCalledWith(2, 'start_local_worker', undefined);
    expect(page.form.controls.password.value).toBe('');
    expect(page.status()?.running).toBe(true);
  });

  it('does not start when saving the configuration failed', async () => {
    vi.mocked(invoke).mockImplementation(() => { throw new Error('Invalid server URL'); });
    await page.start();
    expect(invoke).toHaveBeenCalledOnce();
    expect(page.error()).toContain('Invalid server URL');
    expect(page.busy()).toBe(false);
  });

  it('stops and refreshes the native process status', async () => {
    vi.mocked(invoke).mockResolvedValue({ running: false, legacyService: false, passwordSaved: true, config: {} });
    await page.stop();
    expect(invoke).toHaveBeenNthCalledWith(1, 'stop_local_worker', undefined);
    expect(page.status()?.running).toBe(false);
  });

  it('opens the configured dashboard without transmitting credentials', async () => {
    vi.mocked(invoke).mockResolvedValue(undefined);
    await page.dashboard();
    expect(invoke).toHaveBeenCalledWith('open_server_dashboard', { address: 'http://192.168.178.169:8088' });
  });
});
