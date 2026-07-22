import { Component, OnInit, inject, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import type { Worker } from '@deal-scanner/contracts';

import { ApiService } from './api.service';

@Component({
  standalone: true,
  imports: [MatCardModule, MatChipsModule],
  template: `
    <header class="page-header"><div><p class="eyebrow">Verteilte Analyse</p><h1>Worker</h1><p>Windows-, macOS- und Server-Worker übernehmen nur Jobs, die zu ihren Fähigkeiten passen.</p></div></header>
    @if (error()) { <div class="notice error">{{ error() }}</div> }
    <div class="listing-grid">
      @for (worker of workers(); track worker.id) {
        <mat-card class="listing-card"><div class="row"><span class="status-dot"></span><span>{{ worker.enabled ? 'Aktiv' : 'Deaktiviert' }}</span></div>
          <h3>{{ worker.name }}</h3><p>{{ worker.hostname }} · {{ worker.operatingSystem }}</p>
          <mat-chip-set>@for (capability of worker.capabilities; track capability) { <mat-chip>{{ capability }}</mat-chip> }</mat-chip-set>
          <small>Heartbeat: {{ worker.lastHeartbeatAt }}</small>
        </mat-card>
      } @empty { <div class="empty">Noch kein Worker registriert. Starte <code>pnpm worker</code>.</div> }
    </div>
  `,
})
export class WorkersPage implements OnInit {
  private readonly api = inject(ApiService);
  readonly workers = signal<Worker[]>([]);
  readonly error = signal('');
  async ngOnInit(): Promise<void> {
    try { this.workers.set(await this.api.workers()); } catch (error) { this.error.set(error instanceof Error ? error.message : 'Worker konnten nicht geladen werden'); }
  }
}
