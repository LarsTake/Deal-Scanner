import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';

import { ApiService } from './api.service';
import { OfflineCacheService, type OutboxItem } from './offline-cache.service';
import { OutboxSyncService } from './outbox-sync.service';

@Component({
  standalone: true,
  imports: [MatButtonModule, MatCardModule],
  template: `
    <header class="page-header"><div><p class="eyebrow">Offline-Outbox</p><h1>Konfliktauflösung</h1><p>Änderungen mit veralteter Listing-Version werden niemals still überschrieben.</p></div><button mat-stroked-button (click)="load()">Aktualisieren</button></header>
    @if (message()) { <div class="notice">{{ message() }}</div> }
    <div class="listing-grid wide">
      @for (item of conflicts(); track item.id) {
        <mat-card class="listing-card">
          <h3>{{ item.kind }} · {{ item.aggregateId ?? 'ohne Listing' }}</h3>
          <p>Lokale Basisversion: {{ item.baseVersion ?? '–' }}</p>
          <div class="row actions">
            @if (item.aggregateId) { <button mat-flat-button (click)="retry(item)">Aktuelle Version übernehmen</button> }
            <button mat-stroked-button (click)="discard(item)">Lokale Änderung verwerfen</button>
          </div>
        </mat-card>
      } @empty { <div class="empty">Keine ungelösten Versionskonflikte.</div> }
    </div>
  `,
})
export class ConflictsPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly offline = inject(OfflineCacheService);
  private readonly sync = inject(OutboxSyncService);
  readonly conflicts = signal<OutboxItem[]>([]);
  readonly message = signal('');

  async ngOnInit(): Promise<void> {
    await this.load();
  }

  async load(): Promise<void> {
    this.conflicts.set((await this.offline.pending()).filter((item) => item.status === 'conflict'));
  }

  async retry(item: OutboxItem): Promise<void> {
    if (!item.aggregateId || item.kind !== 'feedback') return;
    try {
      const current = await this.api.listing(item.aggregateId);
      const payload = { ...(item.payload as object), baseListingVersion: current.version };
      await this.offline.retry(item.id, payload, current.version);
      await this.sync.synchronize();
      this.message.set('Konflikt wurde mit der aktuellen Serverversion erneut übertragen.');
      await this.load();
    } catch (error) {
      this.message.set(error instanceof Error ? error.message : 'Konflikt konnte nicht aufgelöst werden');
    }
  }

  async discard(item: OutboxItem): Promise<void> {
    await this.offline.discard(item.id);
    this.message.set('Lokale Änderung wurde verworfen.');
    await this.load();
  }
}
