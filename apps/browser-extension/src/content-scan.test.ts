// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { runScan } from './content';
import { createScan, type ScanState } from './scan';

describe('loaded page traversal and full-description import', () => {
  afterEach(() => vi.unstubAllGlobals());
  const detail = 'https://www.kleinanzeigen.de/s-anzeige/pc/100-228-1234';
  const search = 'https://www.kleinanzeigen.de/s-computer/k0';
  function setup(initial: ScanState, importError?: string) {
    let state = initial;
    const send = vi.fn(async (message) => {
      if (message.type === 'SCAN_STATUS') return state;
      if (message.type === 'SCAN_PROGRESS') { state = message.state; return state; }
      if (message.type === 'IMPORT_VISIBLE_LISTINGS') return { imported: importError ? 0 : 1, results: [], error: importError };
      throw new Error('unexpected message');
    });
    vi.stubGlobal('chrome', { runtime: { sendMessage: send } });
    return { send, state: () => state, stop: () => { state = { ...state, status: 'stopped' }; } };
  }

  it('opens a result, imports its full description, then navigates to the next results page', async () => {
    history.replaceState({}, '', search);
    document.body.innerHTML = `<article><a href="${detail}"><h2>Gaming-PC</h2></a><p>500 €</p><p class="description">Kurztext</p></article><a rel="next" href="/s-computer/seite:2/k0">Weiter</a>`;
    const fixture = setup(createScan(search, { maxPages: 2, maxListings: 10, delaySeconds: 3 }));
    const navigate = vi.fn();
    await runScan(navigate, async () => undefined);
    expect(navigate).toHaveBeenLastCalledWith(detail);
    history.replaceState({}, '', detail);
    document.body.innerHTML = '<h1>Gaming-PC</h1><div id="viewad-price">500 €</div><div id="viewad-description-text">Vollständige Beschreibung: 32 GB RAM, 1 TB SSD, Funktionstest möglich.</div>';
    await runScan(navigate, async () => undefined);
    expect(fixture.send).toHaveBeenCalledWith(expect.objectContaining({
      type: 'IMPORT_VISIBLE_LISTINGS', listings: [expect.objectContaining({ description: expect.stringContaining('32 GB RAM, 1 TB SSD') })],
    }));
    expect(navigate).toHaveBeenLastCalledWith('https://www.kleinanzeigen.de/s-computer/seite:2/k0');
    expect(fixture.state().imported).toBe(1);
  });

  it('honors stop during the pause before making an import request', async () => {
    history.replaceState({}, '', detail);
    const fixture = setup(createScan(detail, { maxPages: 1, maxListings: 1, delaySeconds: 3 }));
    const navigate = vi.fn();
    await runScan(navigate, async () => fixture.stop());
    expect(fixture.send.mock.calls.some(([message]) => message.type === 'IMPORT_VISIBLE_LISTINGS')).toBe(false);
    expect(navigate).not.toHaveBeenCalled();
  });

  it('stops on API errors instead of continuing to other articles', async () => {
    history.replaceState({}, '', detail);
    document.body.innerHTML = '<h1>PC</h1><div id="viewad-price">500 €</div><div id="viewad-description-text">Beschreibung</div>';
    const fixture = setup(createScan(detail, { maxPages: 1, maxListings: 1, delaySeconds: 3 }), 'Token abgelaufen');
    const navigate = vi.fn();
    await runScan(navigate, async () => undefined);
    expect(fixture.state()).toMatchObject({ status: 'error', message: 'Token abgelaufen' });
    expect(navigate).not.toHaveBeenCalled();
  });
});
