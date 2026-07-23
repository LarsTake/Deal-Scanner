import { Injectable } from '@angular/core';

import { SecureTokenStore } from './secure-token.store';

const DEFAULT_DEVELOPMENT_USER_ID = '00000000-0000-4000-8000-000000000001';

export function resolveDevelopmentUserId(): string {
  return localStorage.getItem('deal-scanner-development-user') ?? DEFAULT_DEVELOPMENT_USER_ID;
}

export interface LoopbackPairing {
  apiUrl: string;
  pairingToken: string;
  expiresAtUnix: number;
}

function runsInTauri(): boolean {
  return '__TAURI_INTERNALS__' in window;
}

@Injectable({ providedIn: 'root' })
export class ExtensionLoopbackService {
  constructor(private readonly tokens: SecureTokenStore) {}

  available(): boolean {
    return runsInTauri();
  }

  async start(apiUrl: string): Promise<LoopbackPairing> {
    if (!runsInTauri()) throw new Error('Loopback-Pairing ist nur in der Desktop-App verfügbar.');
    const [{ invoke }, bearerToken] = await Promise.all([
      import('@tauri-apps/api/core'),
      this.tokens.getAccessToken(),
    ]);
    const developmentUserId = resolveDevelopmentUserId();
    return invoke<LoopbackPairing>('start_extension_loopback', {
      request: {
        apiUrl: apiUrl.replace(/\/$/, ''),
        bearerToken,
        developmentUserId,
        ttlSeconds: 300,
      },
    });
  }

  async stop(): Promise<boolean> {
    if (!runsInTauri()) return false;
    const { invoke } = await import('@tauri-apps/api/core');
    return invoke<boolean>('stop_extension_loopback');
  }
}
