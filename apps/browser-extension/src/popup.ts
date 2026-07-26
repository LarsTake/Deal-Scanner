import { validateApiTarget } from './api-target';

const api = document.querySelector<HTMLInputElement>('#api')!;
const token = document.querySelector<HTMLInputElement>('#token')!;
const statusElement = document.querySelector<HTMLElement>('#status')!;
const activate = document.querySelector<HTMLButtonElement>('#activate')!;
document.querySelector<HTMLLabelElement>('label[for=token]')!.textContent = 'Access- oder Geräte-Token';

void Promise.all([
  chrome.storage.sync.get(['apiUrl', 'tokenType']),
  chrome.storage.local.get(['token']),
]).then(([stored, secrets]) => {
  if (stored['apiUrl']) api.value = String(stored['apiUrl']);
  if (secrets['token']) {
    const permanent = stored['tokenType'] === 'pairing';
    token.placeholder = permanent ? 'Geräte-Token ist lokal gespeichert' : 'Access-Token ist lokal gespeichert';
    statusElement.textContent = permanent
      ? 'Dauerhafte Geräteverbindung gespeichert. Zum Ersetzen ein neues Token eintragen.'
      : 'Access-Token gespeichert. Er kann nach Ablauf erneut erforderlich sein.';
  }
});
document.querySelector('#save')?.addEventListener('click', () => void (async () => {
  const value = token.value.trim();
  if (!value) { statusElement.textContent = 'Bitte einen Access- oder Geräte-Token eintragen.'; return; }
  let target;
  try { target = validateApiTarget(api.value); } catch (error) {
    statusElement.textContent = error instanceof Error ? error.message : 'Die API-Adresse ist ungültig.';
    return;
  }
  const { apiUrl, permissionPattern } = target;
  const tokenType = value.includes('.') ? 'bearer' : 'pairing';
  const granted = await chrome.permissions.request({ origins: [permissionPattern] });
  if (!granted) { statusElement.textContent = 'Berechtigung für den API-Host wurde abgelehnt.'; return; }
  await Promise.all([
    chrome.storage.sync.set({ apiUrl, tokenType }),
    chrome.storage.local.set({ token: value }),
  ]);
  token.value = '';
  token.placeholder = tokenType === 'pairing' ? 'Geräte-Token ist lokal gespeichert' : 'Access-Token ist lokal gespeichert';
  statusElement.textContent = tokenType === 'pairing'
    ? 'Dauerhafte Verbindung gespeichert. Der Import startet nur nach deiner Aktion auf Kleinanzeigen.'
    : 'Access-Token gespeichert. Er kann nach Ablauf erneut erforderlich sein.';
})());

activate.addEventListener('click', () => void (async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url) {
    statusElement.textContent = 'Der aktive Tab konnte nicht ermittelt werden.';
    return;
  }
  let current: URL;
  try {
    current = new URL(tab.url);
  } catch {
    statusElement.textContent = 'Diese Browserseite kann nicht analysiert werden.';
    return;
  }
  if (!['http:', 'https:'].includes(current.protocol)) {
    statusElement.textContent = 'Browser- und Einstellungsseiten können nicht analysiert werden.';
    return;
  }
  const origin = `${current.protocol}//${current.hostname}/*`;
  const granted = await chrome.permissions.request({ origins: [origin] });
  if (!granted) {
    statusElement.textContent = 'Die Berechtigung für diese Website wurde abgelehnt.';
    return;
  }
  try {
    try {
      await chrome.tabs.sendMessage(tab.id, { type: 'SHOW_PANEL' });
    } catch {
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
    }
    statusElement.textContent = `Deal Scanner ist auf ${current.hostname} aktiv. Das Steuerfenster ist unten rechts sichtbar.`;
    window.close();
  } catch (error) {
    statusElement.textContent = error instanceof Error ? error.message : 'Die Erweiterung konnte nicht gestartet werden.';
  }
})());

export {};
