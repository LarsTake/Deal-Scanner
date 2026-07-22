import { Injectable } from '@angular/core';
import { DealScannerClient } from '@deal-scanner/api-client';

import { SecureTokenStore } from './secure-token.store';

@Injectable({ providedIn: 'root' })
export class ApiService extends DealScannerClient {
  constructor(tokenStore: SecureTokenStore) {
    super({
      baseUrl: localStorage.getItem('deal-scanner-api-url') ?? 'http://127.0.0.1:8000',
      developmentUserId:
        localStorage.getItem('deal-scanner-development-user') ??
        '00000000-0000-4000-8000-000000000001',
      token: () => tokenStore.getAccessToken(),
    });
  }
}
