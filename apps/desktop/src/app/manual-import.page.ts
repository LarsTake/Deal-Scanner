import { Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import type { MailImport, ProviderSyncRun } from '@deal-scanner/contracts';

import { ApiService } from './api.service';
import { OfflineCacheService } from './offline-cache.service';

@Component({
  standalone: true,
  imports: [MatButtonModule, MatCardModule, MatChipsModule, MatFormFieldModule, MatInputModule, MatSelectModule, ReactiveFormsModule],
  template: `
    <header class="page-header"><div><p class="eyebrow">Erfassung</p><h1>Manueller Import</h1><p>eBay-Links werden ausschließlich über die offizielle Browse API aufgelöst; andere Plattformen benötigen die sichtbaren Angebotsdaten.</p></div></header>
    <mat-card class="form-card"><form [formGroup]="form" (ngSubmit)="submit()">
      <mat-form-field><mat-label>Plattform</mat-label><mat-select formControlName="platform" (valueChange)="platformChanged($event)"><mat-option value="ebay">eBay</mat-option><mat-option value="kleinanzeigen">Kleinanzeigen</mat-option></mat-select></mat-form-field>
      <mat-form-field><mat-label>HTTPS-URL</mat-label><input matInput formControlName="url" /></mat-form-field>
      @if (form.controls.platform.value !== 'ebay') {
        <mat-form-field><mat-label>Externe ID</mat-label><input matInput formControlName="externalId" /></mat-form-field>
        <mat-form-field><mat-label>Titel</mat-label><input matInput formControlName="title" /></mat-form-field>
        <mat-form-field><mat-label>Beschreibung</mat-label><textarea matInput rows="5" formControlName="description"></textarea></mat-form-field>
        <div class="form-row"><mat-form-field><mat-label>Preis</mat-label><input matInput type="number" formControlName="price" /></mat-form-field><mat-form-field><mat-label>Versand</mat-label><input matInput type="number" formControlName="shippingCost" /></mat-form-field></div>
      } @else {
        <p class="notice">Externe ID, Titel, Beschreibung, Preis, Versand und Verkäufer werden nach dem Absenden aus der offiziellen eBay API übernommen.</p>
      }
      <mat-form-field><mat-label>Kategorie</mat-label><mat-select formControlName="categoryProfile"><mat-option value="computer">Computer</mat-option><mat-option value="simracing">Simracing</mat-option><mat-option value="fpv">FPV</mat-option><mat-option value="general">Allgemein</mat-option></mat-select></mat-form-field>
      @if (message()) { <div class="notice">{{ message() }}</div> }
      <button mat-flat-button [disabled]="form.invalid || busy()">Importieren</button>
    </form></mat-card>
    <section class="section-head"><div><p class="eyebrow">Provider</p><h2>Synchronisationsläufe</h2></div><button mat-stroked-button (click)="loadHistory()">Aktualisieren</button></section>
    <div class="listing-grid wide">
      @for (run of syncRuns(); track run.id) {
        <mat-card class="listing-card"><div class="row"><mat-chip>{{ run.status }}</mat-chip><span>{{ run.provider }}</span></div><h3>{{ run.importedCount }} von {{ run.discoveredCount }} importiert</h3><p>Cursor {{ run.cursor ?? '0' }}</p><small>{{ run.startedAt.slice(0, 19) }} {{ run.errorSummary ?? '' }}</small></mat-card>
      } @empty { <div class="empty">Noch keine Providerläufe protokolliert.</div> }
    </div>
    <section class="section-head"><div><p class="eyebrow">E-Mail</p><h2>IMAP-Importe und Quarantäne</h2></div></section>
    <div class="listing-grid wide">
      @for (mail of mailImports(); track mail.id) {
        <mat-card class="listing-card"><div class="row"><mat-chip>{{ mail.status }}</mat-chip><span>{{ mail.receivedAt.slice(0, 10) }}</span></div><h3>{{ mail.subject || mail.messageId }}</h3><p>{{ mail.sender }}</p><small>{{ mail.errorSummary ?? mail.parserVersion }}</small></mat-card>
      } @empty { <div class="empty">Noch keine E-Mail-Importe protokolliert.</div> }
    </div>
  `,
})
export class ManualImportPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly offline = inject(OfflineCacheService);
  readonly busy = signal(false);
  readonly message = signal('');
  readonly syncRuns = signal<ProviderSyncRun[]>([]);
  readonly mailImports = signal<MailImport[]>([]);
  readonly form = new FormGroup({
    platform: new FormControl<'ebay' | 'kleinanzeigen'>('ebay', { nonNullable: true }),
    externalId: new FormControl('resolve-from-url', { nonNullable: true, validators: [Validators.required] }),
    url: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    title: new FormControl('Wird über die offizielle eBay API geladen', { nonNullable: true, validators: [Validators.required] }),
    description: new FormControl('', { nonNullable: true }),
    price: new FormControl(0, { nonNullable: true, validators: [Validators.min(0)] }),
    shippingCost: new FormControl(0, { nonNullable: true, validators: [Validators.min(0)] }),
    categoryProfile: new FormControl<'computer' | 'simracing' | 'fpv' | 'general'>('general', { nonNullable: true }),
  });

  platformChanged(platform: 'ebay' | 'kleinanzeigen'): void {
    if (platform === 'ebay') {
      this.form.patchValue({
        externalId: 'resolve-from-url',
        title: 'Wird über die offizielle eBay API geladen',
        description: '',
        price: 0,
        shippingCost: 0,
      });
      return;
    }
    if (this.form.controls.externalId.value === 'resolve-from-url') {
      this.form.patchValue({ externalId: '', title: '' });
    }
  }

  async ngOnInit(): Promise<void> {
    await this.loadHistory();
  }

  async loadHistory(): Promise<void> {
    try {
      const [runs, mails] = await Promise.all([this.api.providerSyncRuns(), this.api.mailImports()]);
      this.syncRuns.set(runs.items);
      this.mailImports.set(mails);
    } catch (error) {
      this.message.set(error instanceof Error ? error.message : 'Importhistorie konnte nicht geladen werden');
    }
  }

  async submit(): Promise<void> {
    if (this.form.invalid) return;
    this.busy.set(true);
    const value = this.form.getRawValue();
    const payload = {
      ...value,
      price: value.price.toFixed(2),
      shippingCost: value.shippingCost.toFixed(2),
      currency: 'EUR',
      rawData: { source: 'desktopManualImport', capturedAt: new Date().toISOString() },
      providerVersion: 'desktop-manual-v1',
    } as const;
    try {
      await this.api.importListing(payload);
      this.message.set('Angebot importiert und zur Analyse eingeplant.');
      await this.loadHistory();
    } catch (error) {
      const queued = await this.offline
        .enqueue('import', payload)
        .then(() => true)
        .catch(() => false);
      this.message.set(
        queued
          ? 'Offline: Import wurde in der Desktop-Outbox vorgemerkt.'
          : error instanceof Error
            ? error.message
            : 'Import fehlgeschlagen',
      );
    } finally {
      this.busy.set(false);
    }
  }
}
