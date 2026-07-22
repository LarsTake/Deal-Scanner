import { Component, OnInit, inject, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import type { SystemStatus } from '@deal-scanner/contracts';

import { ApiService } from './api.service';

@Component({
  standalone: true,
  imports: [MatCardModule],
  template: `
    <header class="page-header"><div><p class="eyebrow">Betrieb</p><h1>Systemstatus</h1><p>Live-Zustand der API, Warteschlange und registrierten Worker.</p></div></header>
    @if (status()) { <section class="stats"><mat-card><small>Status</small><strong>{{ status()!.status }}</strong></mat-card><mat-card><small>Angebote</small><strong>{{ status()!.listings }}</strong></mat-card><mat-card><small>Offene Jobs</small><strong>{{ status()!.openJobs }}</strong></mat-card><mat-card><small>Worker</small><strong>{{ status()!.workers }}</strong></mat-card></section> }
    @if (error()) { <div class="notice error">{{ error() }}</div> }
  `,
})
export class SystemPage implements OnInit {
  private readonly api = inject(ApiService);
  readonly status = signal<SystemStatus | null>(null);
  readonly error = signal('');
  async ngOnInit(): Promise<void> {
    try { this.status.set(await this.api.systemStatus()); }
    catch (error) { this.error.set(error instanceof Error ? error.message : 'Status nicht verfügbar'); }
  }
}
