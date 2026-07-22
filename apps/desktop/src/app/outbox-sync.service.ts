import { Injectable } from '@angular/core';
import type { FeedbackCreate, ManualImport } from '@deal-scanner/contracts';

import { ApiService } from './api.service';
import { OfflineCacheService, type OutboxItem } from './offline-cache.service';

@Injectable({ providedIn: 'root' })
export class OutboxSyncService {
  constructor(
    private readonly api: ApiService,
    private readonly offline: OfflineCacheService,
  ) {}

  start(): void {
    window.addEventListener('online', () => void this.synchronize());
    if (navigator.onLine) void this.synchronize();
  }

  async synchronize(): Promise<void> {
    await this.offline.synchronize((item) => this.send(item));
  }

  private async send(item: OutboxItem): Promise<void> {
    if (item.kind === 'feedback' && item.aggregateId) {
      await this.api.createFeedback(item.aggregateId, item.payload as FeedbackCreate);
      return;
    }
    if (item.kind === 'import') {
      await this.api.importListing(item.payload as ManualImport, item.id);
    }
  }
}
