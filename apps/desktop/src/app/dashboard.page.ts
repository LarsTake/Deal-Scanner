import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { RouterLink } from '@angular/router';
import type { ListingSummary, SystemStatus } from '@deal-scanner/contracts';

import { ApiService } from './api.service';

@Component({
  standalone: true,
  imports: [MatButtonModule, MatCardModule, MatChipsModule, RouterLink],
  template: `
    <header class="page-header">
      <div><p class="eyebrow">Übersicht</p><h1>Gute Deals. Klare Risiken.</h1><p>Neue Angebote werden regelbasiert geprüft, bevor lokale Modelle zum Einsatz kommen.</p></div>
      <a mat-flat-button routerLink="/search-profiles">Suchauftrag anlegen</a>
    </header>
    @if (error()) { <div class="notice error">{{ error() }}</div> }
    <section class="metric-grid">
      <mat-card><span>Angebote</span><strong>{{ status()?.listings ?? '–' }}</strong><small>im Workspace</small></mat-card>
      <mat-card><span>Offene Analysen</span><strong>{{ status()?.openJobs ?? '–' }}</strong><small>Job-Lease verfügbar</small></mat-card>
      <mat-card><span>Worker</span><strong>{{ status()?.workers ?? '–' }}</strong><small>registriert</small></mat-card>
      <mat-card class="accent"><span>System</span><strong>{{ status()?.status === 'ok' ? 'Online' : '–' }}</strong><small>API und Datenbank</small></mat-card>
    </section>
    <section class="section-head"><div><p class="eyebrow">Zuletzt gesehen</p><h2>Aktuelle Angebote</h2></div><a mat-button routerLink="/listings">Alle anzeigen</a></section>
    <div class="listing-grid">
      @for (listing of listings(); track listing.id) {
        <mat-card class="listing-card">
          <div class="row"><mat-chip>{{ listing.platform }}</mat-chip><span class="age">{{ listing.lastSeenAt.slice(0, 10) }}</span></div>
          <h3>{{ listing.title }}</h3>
          <div class="price">{{ listing.price }} {{ listing.currency }}</div>
          <div class="score-row">
            <div><small>Deal</small><b class="deal">{{ listing.dealScore ?? '–' }}</b></div>
            <div><small>Risiko</small><b class="risk">{{ listing.riskScore ?? '–' }}</b></div>
            <div><small>Status</small><b>{{ listing.analysisStatus }}</b></div>
          </div>
        </mat-card>
      } @empty {
        <div class="empty">Noch keine Angebote. Lege einen Suchauftrag an oder importiere ein sichtbares Angebot.</div>
      }
    </div>
  `,
})
export class DashboardPage implements OnInit {
  private readonly api = inject(ApiService);
  readonly status = signal<SystemStatus | null>(null);
  readonly listings = signal<ListingSummary[]>([]);
  readonly error = signal('');

  async ngOnInit(): Promise<void> {
    try {
      const [status, listings] = await Promise.all([this.api.systemStatus(), this.api.listings()]);
      this.status.set(status);
      this.listings.set(listings.items.slice(0, 6));
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'API nicht erreichbar');
    }
  }
}
