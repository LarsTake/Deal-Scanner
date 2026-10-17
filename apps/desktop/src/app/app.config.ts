import { ApplicationConfig, inject, provideAppInitializer } from '@angular/core';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideHttpClient } from '@angular/common/http';
import { MAT_FORM_FIELD_DEFAULT_OPTIONS } from '@angular/material/form-field';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';
import { OfflineCacheService } from './offline-cache.service';
import { NotificationPollingService } from './notification-polling.service';
import { OutboxSyncService } from './outbox-sync.service';
import { AuthService } from './auth.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(),
    provideAnimationsAsync(),
    { provide: MAT_FORM_FIELD_DEFAULT_OPTIONS, useValue: { subscriptSizing: 'dynamic' } },
    provideAppInitializer(() => inject(OfflineCacheService).initialize()),
    provideAppInitializer(() => {
      // The native control centre opens the remote dashboard in an isolated webview.
      if ('__TAURI_INTERNALS__' in window) return;
      const auth = inject(AuthService);
      const notifications = inject(NotificationPollingService);
      const outbox = inject(OutboxSyncService);
      return auth.initializeFromServer().then(() => {
        notifications.start();
        outbox.start();
      });
    }),
  ],
};
