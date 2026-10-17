import { createScan, type ScanOptions, type ScanState } from './scan';

export interface ScanMessage { type: 'SCAN_START' | 'SCAN_STATUS' | 'SCAN_STOP' | 'SCAN_PROGRESS'; options?: ScanOptions; state?: ScanState; }

// Serialize state updates so a late progress message cannot undo an explicit stop.
let pending: Promise<unknown> = Promise.resolve();
export function handleScanMessage(message: ScanMessage, sender: chrome.runtime.MessageSender): Promise<unknown> {
  const operation = pending.then(async () => {
    const tab = sender.tab ?? (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
    if (tab?.id === undefined) throw new Error('Kein aktiver Browser-Tab.');
    const key = `scan:${tab.id}`;
    const stored = await chrome.storage.session.get(key);
    const current = stored[key] as ScanState | undefined;
    if (message.type === 'SCAN_START') {
      if (current?.status === 'running') throw new Error('Der Durchlauf läuft bereits. Bitte zuerst stoppen.');
      const [config, secrets] = await Promise.all([chrome.storage.sync.get('apiUrl'), chrome.storage.local.get('token')]);
      if (!config['apiUrl'] || !secrets['token']) throw new Error('Zuerst die Scanner-Verbindung speichern.');
      let state = createScan(tab.url ?? '', message.options!);
      await chrome.storage.session.set({ [key]: state });
      try { await chrome.tabs.sendMessage(tab.id, { type: 'SCAN_RUN' }); }
      catch {
        state = { ...state, status: 'error', message: 'Bitte die Kleinanzeigen-Seite neu laden und erneut starten.' };
        await chrome.storage.session.set({ [key]: state });
      }
      return state;
    }
    if (message.type === 'SCAN_STOP' && current) {
      const state = { ...current, status: 'stopped', message: 'Gestoppt. Ein bereits gestarteter Import kann noch abschließen.' };
      await chrome.storage.session.set({ [key]: state });
      return state;
    }
    if (message.type === 'SCAN_PROGRESS') {
      // Progress may only be sent by the content script of the owning tab.
      if (!sender.tab || !current || current.status !== 'running' || message.state?.id !== current.id) return current ?? null;
      await chrome.storage.session.set({ [key]: message.state });
      return message.state;
    }
    return current ?? null;
  });
  pending = operation.catch(() => undefined);
  return operation;
}
