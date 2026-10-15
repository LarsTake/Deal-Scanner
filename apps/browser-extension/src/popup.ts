import { validateApiTarget } from './api-target';

const api = document.querySelector<HTMLInputElement>('#api')!;
const token = document.querySelector<HTMLInputElement>('#token')!;
const statusElement = document.querySelector<HTMLElement>('#status')!;
const saveButton = document.querySelector<HTMLButtonElement>('#save')!;
let storedToken = '';
document.querySelector<HTMLLabelElement>('label[for=token]')!.textContent = 'Access- oder Geräte-Token';

void Promise.all([
  chrome.storage.sync.get(['apiUrl', 'tokenType']),
  chrome.storage.local.get(['token']),
]).then(([stored, secrets]) => {
  if (stored['apiUrl']) api.value = String(stored['apiUrl']);
  if (secrets['token']) {
    storedToken = String(secrets['token']);
    const permanent = stored['tokenType'] === 'pairing';
    token.placeholder = permanent ? 'Geräte-Token ist lokal gespeichert' : 'Access-Token ist lokal gespeichert';
    statusElement.textContent = permanent
      ? 'Dauerhafte Geräteverbindung gespeichert. Zum Ersetzen ein neues Token eintragen.'
      : 'Access-Token gespeichert. Er kann nach Ablauf erneut erforderlich sein.';
  }
});
document.querySelector('#save')?.addEventListener('click', () => void (async () => {
  const value = token.value.trim() || storedToken;
  if (!value) { statusElement.textContent = 'Bitte einen Access- oder Geräte-Token eintragen.'; return; }
  let target;
  try { target = validateApiTarget(api.value); } catch (error) {
    statusElement.textContent = error instanceof Error ? error.message : 'Die API-Adresse ist ungültig.';
    return;
  }
  const { apiUrl, permissionPattern } = target;
  saveButton.disabled = true;
  statusElement.textContent = 'Verbindung wird gespeichert …';
  try {
  const tokenType = value.includes('.') ? 'bearer' : 'pairing';
  const granted = await chrome.permissions.request({ origins: [permissionPattern] });
  if (!granted) { statusElement.textContent = 'Berechtigung für den API-Host wurde abgelehnt.'; return; }
  await Promise.all([
    chrome.storage.sync.set({ apiUrl, tokenType }),
    chrome.storage.local.set({ token: value }),
  ]);
  token.value = '';
  storedToken = value;
  token.placeholder = tokenType === 'pairing' ? 'Geräte-Token ist lokal gespeichert' : 'Access-Token ist lokal gespeichert';
  statusElement.textContent = tokenType === 'pairing'
    ? 'Dauerhafte Verbindung gespeichert. Der Import startet nur nach deiner Aktion auf Kleinanzeigen.'
    : 'Access-Token gespeichert. Er kann nach Ablauf erneut erforderlich sein.';
  } catch (error) {
    statusElement.textContent = error instanceof Error ? error.message : 'Speichern fehlgeschlagen. Bitte erneut versuchen.';
  } finally {
    saveButton.disabled = false;
  }
})());

export {};
