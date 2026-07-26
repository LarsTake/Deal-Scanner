import { Injectable, Injector } from '@angular/core';
import { DealScannerClient } from '@deal-scanner/api-client';

@Injectable({ providedIn: 'root' })
export class ApiService extends DealScannerClient {
  constructor(injector: Injector) {
    super({
      baseUrl: localStorage.getItem('deal-scanner-api-url') ?? 'http://127.0.0.1:8000',
      developmentUserId:
        localStorage.getItem('deal-scanner-development-user') ??
        '00000000-0000-4000-8000-000000000001',
      token: async () => {
        const { AuthService } = await import('./auth.service');
        return injector.get(AuthService).getAccessToken();
      },
    });
  }
}
