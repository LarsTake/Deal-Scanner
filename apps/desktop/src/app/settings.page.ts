import { Component, OnInit, effect, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import type { ExtensionConnection, ExtensionConnectionCreated } from '@deal-scanner/api-client';

import { ApiService } from './api.service';
import { AuthService } from './auth.service';
import { ExtensionLoopbackService, type LoopbackPairing } from './extension-loopback.service';
import { defaultApiUrl } from './connection-target';

@Component({
  standalone: true,
  imports: [MatButtonModule, MatCardModule, MatFormFieldModule, MatInputModule, MatSlideToggleModule, ReactiveFormsModule],
  template: `
    <header class="page-header"><div><p class="eyebrow">Konfiguration</p><h1>Einstellungen</h1><p>Publishable Supabase-Daten sind keine Service-Secrets. Änderungen der API-URL greifen nach einem Neustart.</p></div></header>
    <mat-card class="form-card compact"><form [formGroup]="form" (ngSubmit)="save()">
      <mat-form-field><mat-label>API-URL</mat-label><input matInput formControlName="apiUrl" /></mat-form-field>
      <mat-form-field><mat-label>Supabase-URL</mat-label><input matInput formControlName="supabaseUrl" /></mat-form-field>
      <mat-form-field><mat-label>Supabase Publishable Key</mat-label><input matInput type="password" formControlName="supabaseKey" /></mat-form-field>
      <h2>eBay-Provider</h2>
      <mat-slide-toggle formControlName="ebayEnabled">Provider aktiviert</mat-slide-toggle>
      <mat-form-field><mat-label>Umgebung</mat-label><input matInput formControlName="ebayEnvironment" /></mat-form-field>
      <mat-form-field><mat-label>Marketplace</mat-label><input matInput formControlName="ebayMarketplace" /></mat-form-field>
      <mat-form-field><mat-label>Secret-Referenz</mat-label><input matInput formControlName="ebaySecretReference" /></mat-form-field>
      <small>Hier wird nur der Name der Secret-Quelle gespeichert, niemals das Client-Secret selbst.</small>
      <button mat-flat-button [disabled]="form.invalid">Speichern</button>
      @if (saved()) { <span class="notice">Gespeichert.</span> }
      @if (error()) { <span class="notice error">{{ error() }}</span> }
    </form></mat-card>
    <section class='section-head'><div><p class='eyebrow'>Verfügbarkeit</p><h2>Shop-Restock</h2></div></section>
    <mat-card class='form-card compact'>
      <p>Produktlinks von Otto, MediaMarkt, Saturn, Amazon oder Müller; eine URL pro Zeile. Meldungen kommen beim Wechsel auf verfügbar.</p>
      <mat-form-field><mat-label>Produktlinks</mat-label><textarea matInput [formControl]='restockUrls' rows='5'></textarea></mat-form-field>
      <mat-slide-toggle [formControl]='restockEnabled'>Überwachung aktiv</mat-slide-toggle>
      <mat-slide-toggle [formControl]='restockNtfy'>Auch per ntfy melden</mat-slide-toggle>
      <div class='row'><button mat-flat-button type='button' (click)='saveRestock()'>Restock speichern</button>
        <button mat-stroked-button type='button' (click)='checkRestock()'>Verfügbarkeit prüfen</button></div>
      @if (restockMessage()) { <div class='notice'>{{ restockMessage() }}</div> }
      @if (restockError()) { <div class='notice error'>{{ restockError() }}</div> }
    </mat-card>
    <section class='section-head'><div><p class='eyebrow'>Browser-Erweiterung</p><h2>Dauerhafte Kontoverbindung</h2></div></section>
    <mat-card class='form-card compact'>
      <p>Die Verbindung wird nach deiner Anmeldung als widerrufbares Geräte-Token erstellt. Passwort und Supabase-Sitzung bleiben in der Desktop-App.</p>
      @if (!auth.userEmail()) {
        <div class='notice'>Bitte zuerst mit E-Mail und Passwort anmelden.</div>
      } @else {
        <div class='notice'>Angemeldet als {{ auth.userEmail() }}</div>
        <mat-form-field><mat-label>Gerätename</mat-label><input matInput [formControl]='connectionName' /></mat-form-field>
        <button mat-flat-button type='button' [disabled]='connectionName.invalid || connectionBusy()' (click)='createPermanentConnection()'>
          {{ connectionBusy() ? 'Verbindung wird erstellt…' : 'Dauerhafte Verbindung erstellen' }}
        </button>
        @if (createdConnection(); as created) {
          <div class='notice'>Das Geräte-Token wird nur jetzt vollständig angezeigt. Speichere beide Werte in der Browser-Erweiterung.</div>
          <mat-form-field><mat-label>API-Adresse</mat-label><input matInput readonly [value]='form.controls.apiUrl.value' /></mat-form-field>
          <mat-form-field><mat-label>Geräte-Token</mat-label><input matInput readonly [value]='created.token' /></mat-form-field>
        }
        @for (connection of permanentConnections(); track connection.id) {
          <div class='row'>
            <span><strong>{{ connection.displayName }}</strong><small>Erstellt: {{ connectionCreatedAt(connection) }}</small></span>
            <button mat-stroked-button type='button' (click)='revokePermanentConnection(connection.id)'>Widerrufen</button>
          </div>
        }
      }
      @if (connectionError()) { <div class='notice error'>{{ connectionError() }}</div> }
    </mat-card>
    <section class="section-head"><div><p class="eyebrow">Browser-Erweiterung</p><h2>Sichere Desktop-Kopplung</h2></div></section>
    <mat-card class="form-card compact">
      @if (!loopback.available()) {
        <div class="notice">Die native Loopback-Kopplung ist nur in der installierten Desktop-App verfügbar.</div>
      } @else {
        <p>Erzeugt für fünf Minuten einen lokalen Import-Endpunkt. Das Supabase-JWT bleibt im Desktop-Prozess.</p>
        <div class="row">
          <button mat-flat-button type="button" (click)="startLoopback()">Neue Kopplung erzeugen</button>
          @if (pairing()) { <button mat-stroked-button type="button" (click)="stopLoopback()">Widerrufen</button> }
        </div>
        @if (pairing(); as current) {
          <mat-form-field><mat-label>API-Adresse für die Erweiterung</mat-label><input matInput readonly [value]="current.apiUrl" /></mat-form-field>
          <mat-form-field><mat-label>Pairing-Token</mat-label><input matInput readonly [value]="current.pairingToken" /></mat-form-field>
          <small>Gültig bis {{ expiresAt(current) }}. Beide Werte in der Erweiterung speichern; der Token wird danach automatisch ungültig.</small>
        }
        @if (loopbackError()) { <div class="notice error">{{ loopbackError() }}</div> }
      }
    </mat-card>
  `,
})
export class SettingsPage implements OnInit {
  readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  readonly loopback = inject(ExtensionLoopbackService);
  readonly saved = signal(false);
  readonly restockUrls = new FormControl('', { nonNullable: true });
  readonly restockEnabled = new FormControl(false, { nonNullable: true });
  readonly restockNtfy = new FormControl(false, { nonNullable: true });
  readonly restockMessage = signal('');
  readonly restockError = signal('');
  readonly error = signal('');
  readonly pairing = signal<LoopbackPairing | null>(null);
  readonly loopbackError = signal('');
  readonly permanentConnections = signal<ExtensionConnection[]>([]);
  readonly createdConnection = signal<ExtensionConnectionCreated | null>(null);
  readonly connectionBusy = signal(false);
  readonly connectionError = signal('');
  readonly connectionName = new FormControl('Browser-Erweiterung', {
    nonNullable: true,
    validators: [Validators.required, Validators.maxLength(120)],
  });
  readonly form = new FormGroup({
    apiUrl: new FormControl(localStorage.getItem('deal-scanner-api-url') ?? defaultApiUrl(window.location, '__TAURI_INTERNALS__' in window), { nonNullable: true, validators: [Validators.required] }),
    supabaseUrl: new FormControl(localStorage.getItem('deal-scanner-supabase-url') ?? '', { nonNullable: true }),
    supabaseKey: new FormControl(localStorage.getItem('deal-scanner-supabase-key') ?? '', { nonNullable: true }),
    ebayEnabled: new FormControl(true, { nonNullable: true }),
    ebayEnvironment: new FormControl('sandbox', { nonNullable: true, validators: [Validators.required] }),
    ebayMarketplace: new FormControl('EBAY_DE', { nonNullable: true, validators: [Validators.required] }),
    ebaySecretReference: new FormControl('env:DEAL_SCANNER_EBAY_CLIENT_SECRET', { nonNullable: true }),
  });

  constructor() {
    effect(() => {
      if (this.auth.userEmail()) {
        void this.loadPermanentConnections();
      } else {
        this.permanentConnections.set([]);
        this.createdConnection.set(null);
      }
    });
  }

  async ngOnInit(): Promise<void> {
    try {
      const configuration = await this.api.restockConfiguration();
      this.restockUrls.setValue((configuration.urls ?? []).join('\n'));
      this.restockEnabled.setValue(configuration.enabled);
      this.restockNtfy.setValue(configuration.ntfyEnabled);
    } catch { /* Restock settings remain editable while offline. */ }
    try {
      const ebay = (await this.api.providerConfigurations()).find((item) => item.provider === 'ebay');
      if (ebay) {
        const settings = ebay.settings ?? {};
        this.form.patchValue({
          ebayEnabled: ebay.enabled,
          ebayEnvironment: String(settings['environment'] ?? 'sandbox'),
          ebayMarketplace: String(settings['marketplaceId'] ?? 'EBAY_DE'),
          ebaySecretReference: ebay.secretReference ?? '',
        });
      }
    } catch {
      // Local connection settings remain editable while the API is offline.
    }
  }

  async save(): Promise<void> {
    const value = this.form.getRawValue();
    this.error.set('');
    localStorage.setItem('deal-scanner-api-url', value.apiUrl.replace(/\/$/, ''));
    if (value.supabaseUrl && value.supabaseKey) this.auth.configure(value.supabaseUrl, value.supabaseKey);
    try {
      await this.api.configureProvider('ebay', {
        enabled: value.ebayEnabled,
        settings: { environment: value.ebayEnvironment, marketplaceId: value.ebayMarketplace },
        secretReference: value.ebaySecretReference || null,
      });
      this.saved.set(true);
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Provider-Konfiguration konnte nicht gespeichert werden');
    }
  }

  async saveRestock(): Promise<void> {
    this.restockError.set('');
    this.restockMessage.set('');
    try {
      await this.api.saveRestockConfiguration({
        urls: this.restockUrls.value.split('\n').map((url) => url.trim()).filter(Boolean),
        enabled: this.restockEnabled.value,
        desktopEnabled: true, ntfyEnabled: this.restockNtfy.value,
        notifyOnFirstRun: false, intervalSeconds: 300,
      });
      this.restockMessage.set('Restock-Einstellungen gespeichert. Der Scheduler prüft alle fünf Minuten.');
    } catch (error) {
      this.restockError.set(error instanceof Error ? error.message : 'Restock konnte nicht gespeichert werden.');
    }
  }

  async checkRestock(): Promise<void> {
    this.restockError.set('');
    try {
      const result = await this.api.checkRestock();
      const states = result['states'] as Record<string, { available?: boolean | null; title?: string }>;
      const summaries = Object.entries(states ?? {}).map(([url, state]) =>
        `${state.title ?? url}: ${state.available === true ? 'verfügbar' : state.available === false ? 'nicht verfügbar' : 'unbekannt'}`);
      this.restockMessage.set(`${String(result['checked'] ?? 0)} Produktseiten geprüft. ${summaries.join(' · ')}`);
    } catch (error) {
      this.restockError.set(error instanceof Error ? error.message : 'Restock-Prüfung fehlgeschlagen.');
    }
  }

  private async loadPermanentConnections(): Promise<void> {
    try {
      this.permanentConnections.set(await this.api.extensionConnections());
      this.connectionError.set('');
    } catch (error) {
      this.connectionError.set(
        error instanceof Error ? error.message : 'Geräteverbindungen konnten nicht geladen werden',
      );
    }
  }

  async createPermanentConnection(): Promise<void> {
    const displayName = this.connectionName.value.trim();
    if (!this.auth.userEmail() || !displayName || this.connectionBusy()) return;
    this.connectionBusy.set(true);
    this.connectionError.set('');
    try {
      this.createdConnection.set(
        await this.api.createExtensionConnection({ displayName }),
      );
      await this.loadPermanentConnections();
    } catch (error) {
      this.connectionError.set(
        error instanceof Error ? error.message : 'Geräteverbindung konnte nicht erstellt werden',
      );
    } finally {
      this.connectionBusy.set(false);
    }
  }

  async revokePermanentConnection(connectionId: string): Promise<void> {
    this.connectionError.set('');
    try {
      await this.api.revokeExtensionConnection(connectionId);
      if (this.createdConnection()?.id === connectionId) this.createdConnection.set(null);
      await this.loadPermanentConnections();
    } catch (error) {
      this.connectionError.set(
        error instanceof Error ? error.message : 'Geräteverbindung konnte nicht widerrufen werden',
      );
    }
  }

  connectionCreatedAt(connection: ExtensionConnection): string {
    return new Date(connection.createdAt).toLocaleString('de-DE');
  }

  async startLoopback(): Promise<void> {
    this.loopbackError.set('');
    try {
      this.pairing.set(await this.loopback.start(this.form.controls.apiUrl.value));
    } catch (error) {
      this.loopbackError.set(
        error instanceof Error
          ? error.message
          : typeof error === 'string'
            ? error
            : 'Loopback-Kopplung konnte nicht gestartet werden',
      );
    }
  }

  async stopLoopback(): Promise<void> {
    await this.loopback.stop();
    this.pairing.set(null);
  }

  expiresAt(pairing: LoopbackPairing): string {
    return new Date(pairing.expiresAtUnix * 1000).toLocaleTimeString('de-DE');
  }
}
