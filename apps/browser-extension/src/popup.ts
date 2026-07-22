const api = document.querySelector<HTMLInputElement>('#api')!;
const token = document.querySelector<HTMLInputElement>('#token')!;
const statusElement = document.querySelector<HTMLElement>('#status')!;

void chrome.storage.sync.get(['apiUrl']).then((stored) => { if (stored['apiUrl']) api.value = String(stored['apiUrl']); });
document.querySelector('#save')?.addEventListener('click', () => void (async () => {
  const value = token.value.trim();
  const apiUrl = api.value.trim().replace(/\/$/, '');
  const origin = new URL(apiUrl).origin;
  if (origin.startsWith('https://')) {
    const granted = await chrome.permissions.request({ origins: [`${origin}/*`] });
    if (!granted) { statusElement.textContent = 'Berechtigung für den API-Host wurde abgelehnt.'; return; }
  }
  await Promise.all([
    chrome.storage.sync.set({ apiUrl, tokenType: value.includes('.') ? 'bearer' : 'pairing' }),
    chrome.storage.local.set({ token: value }),
  ]);
  statusElement.textContent = 'Gespeichert. Der Import startet ausschließlich über die Schaltfläche auf Kleinanzeigen.';
})());

export {};
