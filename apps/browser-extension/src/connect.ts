import { validateApiTarget } from './api-target';

// Runs in the active scanner tab's isolated world. No account password or JWT is transferred.
export function requestScannerConnection(): Promise<{ apiUrl: string; token: string }> {
  const nonce = crypto.randomUUID();
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      window.removeEventListener('message', receive);
      reject(new Error('Keine Antwort. Bitte im aktualisierten Scanner-Dashboard im Browser anmelden.'));
    }, 15000);
    function receive(event: MessageEvent): void {
      if (event.source !== window || event.origin !== location.origin || event.data?.type !== 'DEAL_SCANNER_CONNECTED'
          || event.data.nonce !== nonce) return;
      clearTimeout(timeout);
      window.removeEventListener('message', receive);
      if (event.data.error) reject(new Error(String(event.data.error)));
      else resolve({ apiUrl: event.data.apiUrl, token: event.data.token });
    }
    window.addEventListener('message', receive);
    window.postMessage({ type: 'DEAL_SCANNER_CONNECT', nonce }, location.origin);
  });
}

export interface PreparedScanner { tabId: number; apiUrl: string; permissionPattern: string; }

export async function prepareActiveScanner(): Promise<PreparedScanner> {
  const tab = (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
  if (tab?.id === undefined) throw new Error('Bitte das Scanner-Dashboard im Browser öffnen.');
  const [descriptor] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => document.querySelector<HTMLMetaElement>('meta[name="deal-scanner-api"]')?.content ?? '',
  });
  if (!descriptor?.result) throw new Error('Bitte im aktualisierten Scanner-Dashboard im Browser anmelden.');
  const target = validateApiTarget(descriptor.result);
  return { tabId: tab.id, ...target };
}

export async function connectPreparedScanner(target: PreparedScanner): Promise<{ apiUrl: string; token: string }> {
  // First operation: preserve the popup button's user gesture for Chrome's permission prompt.
  const granted = await chrome.permissions.request({ origins: [target.permissionPattern] });
  if (!granted) throw new Error('Berechtigung für den Scanner-Server wurde abgelehnt.');
  const [response] = await chrome.scripting.executeScript({ target: { tabId: target.tabId }, func: requestScannerConnection });
  const result = response?.result;
  if (!result || typeof result.token !== 'string' || !result.token || result.apiUrl !== target.apiUrl) {
    throw new Error('Die Scanner-Verbindung ist unvollständig. Bitte erneut anmelden und verbinden.');
  }
  await Promise.all([
    chrome.storage.sync.set({ apiUrl: target.apiUrl, tokenType: 'pairing' }),
    chrome.storage.local.set({ token: result.token }),
  ]);
  return result;
}
