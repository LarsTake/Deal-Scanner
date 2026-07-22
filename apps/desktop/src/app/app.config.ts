import { ApplicationConfig, inject, provideAppInitializer } from '@angular/core';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';
import { OfflineCacheService } from './offline-cache.service';
import { NotificationPollingService } from './notification-polling.service';
import { OutboxSyncService } from './outbox-sync.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(),
    provideAnimationsAsync(),
    provideAppInitializer(() => inject(OfflineCacheService).initialize()),
    provideAppInitializer(() => inject(NotificationPollingService).start()),
    provideAppInitializer(() => inject(OutboxSyncService).start()),
  ],
};
