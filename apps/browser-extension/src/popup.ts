import { validateApiTarget } from './api-target';
import { connectPreparedScanner, prepareActiveScanner, type PreparedScanner } from './connect';
import type { ScanState } from './scan';

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

const connect = document.querySelector<HTMLButtonElement>('#connect')!;
let preparedScanner: PreparedScanner | null = null;
let prepareError = 'Bitte das Scanner-Dashboard im Browser öffnen und die Erweiterung dort erneut öffnen.';
connect.disabled = true;
void prepareActiveScanner().then((target) => { preparedScanner = target; })
  .catch((error: unknown) => { if (error instanceof Error) prepareError = error.message; })
  .finally(() => { connect.disabled = false; });

connect.addEventListener('click', () => void (async () => {
  if (!preparedScanner) { statusElement.textContent = prepareError; return; }
  connect.disabled = true;
  statusElement.textContent = 'Scanner-Konto wird verbunden …';
  try {
    const result = await connectPreparedScanner(preparedScanner);
    api.value = result.apiUrl; storedToken = result.token; token.value = '';
    statusElement.textContent = 'Mit deinem Scanner-Konto verbunden. API und Geräte-Token sind gespeichert.';
  } catch (error) { statusElement.textContent = error instanceof Error ? error.message : 'Verbindung fehlgeschlagen.'; }
  finally { connect.disabled = false; }
})());

const scanStatus = document.querySelector<HTMLElement>('#scan-status')!;
const showScan = (state: (ScanState & { error?: string }) | null) => {
  if (state) scanStatus.textContent = state.error ?? `${state.message} (${state.imported ?? 0} importiert)`;
};
void chrome.runtime.sendMessage({ type: 'SCAN_STATUS' }).then(showScan).catch(() => undefined);
document.querySelector('#scan-start')?.addEventListener('click', () => void (async () => {
  try {
    showScan(await chrome.runtime.sendMessage({ type: 'SCAN_START', options: {
      maxPages: Number(document.querySelector<HTMLInputElement>('#pages')!.value),
      maxListings: Number(document.querySelector<HTMLInputElement>('#listings')!.value),
      delaySeconds: Number(document.querySelector<HTMLInputElement>('#delay')!.value),
    } }));
  } catch (error) { scanStatus.textContent = String(error); }
})());
document.querySelector('#scan-stop')?.addEventListener('click', () => void (async () => {
  try { showScan(await chrome.runtime.sendMessage({ type: 'SCAN_STOP' })); }
  catch (error) { scanStatus.textContent = String(error); }
})());
