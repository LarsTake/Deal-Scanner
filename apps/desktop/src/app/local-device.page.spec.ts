import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LocalDevicePage } from './local-device.page';

const invoke = vi.fn<(name: string, args?: Record<string, unknown>) => Promise<unknown>>();
let page: LocalDevicePage;

describe('local worker controls', () => {
  beforeEach(() => {
    localStorage.clear();
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
    expect(invoke).toHaveBeenCalledWith('open_server_dashboard', { address: 'http://127.0.0.1:8000' });
  });

  it('passes the selected image mode and local model roles to the worker', async () => {
    invoke.mockResolvedValue({ running: true, config: {} });
    page.form.patchValue({ localMode: true, images: true, visionModel: 'gemma4:12b', reasoningModel: 'gpt-oss:20b' });
    await page.start();
    expect(invoke).toHaveBeenCalledWith('save_local_worker', expect.objectContaining({
      config: expect.objectContaining({ localMode: true, images: true, visionModel: 'gemma4:12b', reasoningModel: 'gpt-oss:20b' }),
    }));
  });

  it('reuses server-provided public auth settings without manual Supabase fields', async () => {
    localStorage.setItem('deal-scanner-api-url', 'http://192.168.178.169:8088');
    localStorage.setItem('deal-scanner-supabase-url', 'https://project.example.test');
    localStorage.setItem('deal-scanner-supabase-key', 'sb_publishable_fixture');
    invoke.mockResolvedValue({ running: true, config: {} });
    await page.start();
    expect(invoke).toHaveBeenCalledWith('save_local_worker', expect.objectContaining({
      config: expect.objectContaining({ serverUrl: 'http://192.168.178.169:8088', supabaseUrl: 'https://project.example.test', publishableKey: 'sb_publishable_fixture' }),
    }));
  });

  it('enables web research by default and supports a fully local request', async () => {
    invoke.mockResolvedValue({ answer: 'Testantwort', sources: [] });
    page.question.setValue('Prüfe dieses Angebot');
    await page.research();
    expect(invoke).toHaveBeenLastCalledWith('research_local', { question: 'Prüfe dieses Angebot', useInternet: true });
    page.useInternet.setValue(false);
    await page.research();
    expect(invoke).toHaveBeenLastCalledWith('research_local', { question: 'Prüfe dieses Angebot', useInternet: false });
    expect(page.researchResult()?.answer).toBe('Testantwort');
    expect(page.researchBusy()).toBe(false);
  });

  it('preserves a separately entered worker account when dashboard email is cached', async () => {
    localStorage.setItem('deal-scanner-user-email', 'dashboard@example.test');
    page.form.controls.email.setValue('worker@example.test');
    invoke.mockResolvedValue({ running: false, config: {} });
    await page.save();
    expect(invoke).toHaveBeenCalledWith('save_local_worker', expect.objectContaining({
      config: expect.objectContaining({ email: 'worker@example.test' }),
    }));
  });

  it('shows research failures without retaining a previous answer', async () => {
    invoke.mockRejectedValue(new Error('Ollama ist nicht erreichbar'));
    await page.research();
    expect(page.researchResult()).toBeNull();
    expect(page.researchError()).toContain('Ollama ist nicht erreichbar');
    expect(page.researchBusy()).toBe(false);
  });
});
