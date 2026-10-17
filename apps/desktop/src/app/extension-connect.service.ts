import { Injectable, inject } from '@angular/core';
import { AuthService } from './auth.service';
import { ApiService } from './api.service';
import { defaultApiUrl } from './connection-target';

@Injectable({ providedIn: 'root' })
export class ExtensionConnectService {
  private readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  private busy = false;
  private marker?: HTMLMetaElement;
  private readonly listener = (event: MessageEvent) => void this.receive(event);

  start(): void {
    // Chrome connects to the web dashboard. Native windows are not browser tabs.
    if ('__TAURI_INTERNALS__' in window || this.marker) return;
    const marker = document.createElement('meta');
    marker.name = 'deal-scanner-api';
    marker.content = localStorage.getItem('deal-scanner-api-url') ?? defaultApiUrl(window.location, false);
    document.head.append(marker);
    this.marker = marker;
    window.addEventListener('message', this.listener);
  }

  ngOnDestroy(): void {
    window.removeEventListener('message', this.listener);
    this.marker?.remove();
  }

  private async receive(event: MessageEvent): Promise<void> {
    if (event.source !== window || event.origin !== location.origin || event.data?.type !== 'DEAL_SCANNER_CONNECT'
        || typeof event.data.nonce !== 'string' || event.data.nonce.length > 100 || this.busy) return;
    const nonce: string = event.data.nonce;
    this.busy = true;
    try {
      if (!this.auth.userEmail()) throw new Error('Bitte zuerst im Scanner-Dashboard anmelden.');
      const apiUrl = (localStorage.getItem('deal-scanner-api-url') ?? defaultApiUrl(window.location, false)).replace(/\/$/, '');
      const created = await this.api.createExtensionConnection({ displayName: 'Chrome · automatische Kopplung' });
      window.postMessage({ type: 'DEAL_SCANNER_CONNECTED', nonce, apiUrl, token: created.token }, location.origin);
    } catch (error) {
      window.postMessage({ type: 'DEAL_SCANNER_CONNECTED', nonce,
        error: error instanceof Error ? error.message : 'Verbindung fehlgeschlagen.' }, location.origin);
    } finally { this.busy = false; }
  }
}
