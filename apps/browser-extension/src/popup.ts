import { validateApiTarget } from './api-target';

const api = document.querySelector<HTMLInputElement>('#api')!;
const token = document.querySelector<HTMLInputElement>('#token')!;
const statusElement = document.querySelector<HTMLElement>('#status')!;

void chrome.storage.sync.get(['apiUrl']).then((stored) => { if (stored['apiUrl']) api.value = String(stored['apiUrl']); });
document.querySelector('#save')?.addEventListener('click', () => void (async () => {
  const value = token.value.trim();
  if (!value) { statusElement.textContent = 'Bitte einen Access- oder Pairing-Token eintragen.'; return; }
  let target;
  try { target = validateApiTarget(api.value); } catch (error) {
    statusElement.textContent = error instanceof Error ? error.message : 'Die API-Adresse ist ungültig.';
    return;
  }
  const { apiUrl, permissionPattern } = target;
  const granted = await chrome.permissions.request({ origins: [permissionPattern] });
  if (!granted) { statusElement.textContent = 'Berechtigung für den API-Host wurde abgelehnt.'; return; }
  await Promise.all([
    chrome.storage.sync.set({ apiUrl, tokenType: value.includes('.') ? 'bearer' : 'pairing' }),
    chrome.storage.local.set({ token: value }),
  ]);
  statusElement.textContent = 'Gespeichert. Der Import startet ausschließlich über die Schaltfläche auf Kleinanzeigen.';
})());

export {};
