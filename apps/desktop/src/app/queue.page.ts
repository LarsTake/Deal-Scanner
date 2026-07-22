import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import type { AnalysisJob } from '@deal-scanner/contracts';

import { ApiService } from './api.service';

@Component({
  standalone: true,
  imports: [MatButtonModule, MatCardModule, MatChipsModule],
  template: `
    <header class="page-header"><div><p class="eyebrow">Worker</p><h1>Analysewarteschlange</h1><p>Leases, Wiederholungen und Dead-Letter-Zustände bleiben sichtbar.</p></div><button mat-stroked-button (click)="load()">Aktualisieren</button></header>
    @if (error()) { <div class="notice error">{{ error() }}</div> }
    <div class="listing-grid wide">
      @for (job of jobs(); track job.id) {
        <mat-card class="listing-card">
          <div class="row"><mat-chip>{{ job.status }}</mat-chip><span>Priorität {{ job.priority }}</span></div>
          <h3>{{ job.jobType }}</h3>
          <p>Listing {{ job.listingId }}</p>
          <div class="score-row">
            <div><small>Versuche</small><b>{{ job.attempts }}</b></div>
            <div><small>Capability</small><b>{{ job.requiredCapability }}</b></div>
            <div><small>Lease</small><b>{{ job.leaseExpiresAt ? job.leaseExpiresAt.slice(11, 19) : '–' }}</b></div>
          </div>
        </mat-card>
      } @empty { <div class="empty">Keine Analysejobs vorhanden.</div> }
    </div>
  `,
})
export class QueuePage implements OnInit {
  private readonly api = inject(ApiService);
  readonly jobs = signal<AnalysisJob[]>([]);
  readonly error = signal('');

  async ngOnInit(): Promise<void> {
    await this.load();
  }

  async load(): Promise<void> {
    try {
      this.jobs.set(await this.api.jobs());
      this.error.set('');
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Jobs konnten nicht geladen werden');
    }
  }
}
