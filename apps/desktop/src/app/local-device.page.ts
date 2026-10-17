import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';

interface WorkerConfig {
  serverUrl: string; executable: string; supabaseUrl: string; publishableKey: string;
  email: string; textModel: string; visionModel: string; images: boolean; passwordFile: string;
}
interface WorkerStatus { running: boolean; legacyService: boolean; passwordSaved: boolean; config: WorkerConfig; }

@Component({
  standalone: true,
  imports: [ReactiveFormsModule, MatButtonModule, MatCardModule, MatFormFieldModule, MatInputModule, MatSlideToggleModule],
  template: `
    <header class="page-header"><div><p class="eyebrow">Dieses Gerät</p><h1>Dein lokaler KI-Worker</h1>
      <p>Das Dashboard läuft auf dem ThinkCentre. Hier steuerst du ausschließlich die KI auf diesem Computer.</p></div></header>
    @if (!native) {
      <p class="notice">Diese Steuerung benötigt die installierte Deal-Scanner-App für Windows oder Mac.</p>
    } @else {
      @if (error()) { <p class="notice error" role="alert">{{ error() }}</p> }
      @if (message()) { <p class="notice" role="status">{{ message() }}</p> }
      <div class="two-column">
        <mat-card class="form-card"><h2>Dashboard & Worker</h2>
          <p>{{ status()?.running ? 'Worker-Prozess läuft' : 'Worker ist gestoppt' }}</p>
          <small>Der Prozessstatus bestätigt noch keine erfolgreiche KI-Auswertung. Anmeldung und Heartbeat siehst du im Server-Dashboard unter Worker.</small>
          @if (status()?.legacyService) { <p class="notice">Dein bisheriger Mac-Hintergrunddienst ist aktiv. Stopp deaktiviert auch dessen Autostart. Danach übernimmt diese App.</p> }
          <div class="actions">
            <button mat-flat-button [disabled]="busy()" (click)="dashboard()">ThinkCentre-Dashboard öffnen</button>
            <button mat-stroked-button [disabled]="busy() || !!status()?.running" (click)="start()">Worker aktivieren</button>
            <button mat-stroked-button [disabled]="busy() || !status()?.running" (click)="stop()">Worker deaktivieren</button>
          </div>
          <small>Das Server-Dashboard öffnet sich im Standardbrowser. Nur diese App darf den lokalen Worker steuern.</small>
          <p>Der App-Worker arbeitet bei minimiertem Fenster weiter. Beim Beenden der App wird er gestoppt. Kein neuer System-Autostart wird eingerichtet.</p>
          <p>Ollama und die gewählten Modelle müssen lokal installiert sein und laufen. Bildanalyse ist optional und kann deutlich länger dauern.</p>
        </mat-card>
        <mat-card class="form-card"><h2>Lokale Einstellungen</h2>
          <form [formGroup]="form" (ngSubmit)="save()">
            <mat-form-field><mat-label>ThinkCentre-Adresse</mat-label><input matInput formControlName="serverUrl" placeholder="http://192.168.178.169:8088" /></mat-form-field>
            <mat-form-field><mat-label>Worker-Programmdatei</mat-label><input matInput formControlName="executable" /></mat-form-field>
            <button mat-stroked-button type="button" (click)="choose()" [disabled]="busy()">Installierten Worker auswählen</button>
            <small>Mac: .venv/bin/deal-scanner-worker · Windows: .venv/Scripts/deal-scanner-worker.exe. Die App enthält noch keine gebündelte Python-Laufzeit.</small>
            <mat-form-field><mat-label>Textmodell in Ollama</mat-label><input matInput formControlName="textModel" /></mat-form-field>
            <mat-slide-toggle formControlName="images">Zusätzlich Bilder analysieren</mat-slide-toggle>
            @if (form.controls.images.value) {
              <mat-form-field><mat-label>Installiertes Vision-Modell</mat-label><input matInput formControlName="visionModel" /></mat-form-field>
            }
            <h3>Dienstanmeldung</h3>
            <small>Unabhängig von der Anmeldung im Dashboard. Keine Datenbankpasswörter und keine Service-Role-Keys eingeben.</small>
            <mat-form-field><mat-label>Supabase-URL</mat-label><input matInput formControlName="supabaseUrl" /></mat-form-field>
            <mat-form-field><mat-label>Publishable Key</mat-label><input matInput formControlName="publishableKey" /></mat-form-field>
            <mat-form-field><mat-label>Scanner-E-Mail</mat-label><input matInput type="email" formControlName="email" /></mat-form-field>
            <mat-form-field><mat-label>Scanner-Passwort {{ status()?.passwordSaved ? '(bereits hinterlegt)' : '' }}</mat-label><input matInput type="password" formControlName="password" autocomplete="new-password" /></mat-form-field>
            <small>Leer lassen, um das hinterlegte Passwort zu behalten. Es wird lokal mit Benutzerzugriff gespeichert, nicht verschlüsselt und nicht zum Dashboard übertragen.</small>
            <button mat-flat-button [disabled]="busy() || !!status()?.running">Einstellungen speichern</button>
            @if (status()?.running) { <small>Für Änderungen zuerst den Worker stoppen.</small> }
          </form>
        </mat-card>
      </div>
    }
  `,
  styles: `.actions { display: flex; flex-wrap: wrap; gap: 12px; margin: 24px 0; } small { display: block; margin-bottom: 14px; }`,
})
export class LocalDevicePage implements OnInit, OnDestroy {
  readonly native = '__TAURI_INTERNALS__' in window;
  readonly status = signal<WorkerStatus | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  readonly form = new FormGroup({
    serverUrl: new FormControl('http://192.168.178.169:8088', { nonNullable: true }),
    executable: new FormControl('', { nonNullable: true }),
    textModel: new FormControl('', { nonNullable: true }),
    visionModel: new FormControl('', { nonNullable: true }),
    images: new FormControl(false, { nonNullable: true }),
    supabaseUrl: new FormControl('', { nonNullable: true }),
    publishableKey: new FormControl('', { nonNullable: true }),
    email: new FormControl('', { nonNullable: true }),
    password: new FormControl('', { nonNullable: true }),
  });
  private timer?: ReturnType<typeof setInterval>;
  async ngOnInit(): Promise<void> {
    if (!this.native) return;
    await this.perform(async () => {
      await this.refresh(true);
      await this.invoke('open_server_dashboard', { address: this.form.controls.serverUrl.value });
      this.timer = setInterval(() => { if (!this.busy()) void this.refresh().catch(() => undefined); }, 5000);
    });
  }
  ngOnDestroy(): void { clearInterval(this.timer); }
  private async invoke<T>(name: string, args?: Record<string, unknown>): Promise<T> {
    const { invoke } = await import('@tauri-apps/api/core');
    return invoke<T>(name, args);
  }
  private async refresh(fill = false): Promise<void> {
    const status = await this.invoke<WorkerStatus>('local_worker_status');
    this.status.set(status);
    if (fill) this.form.patchValue(status.config);
  }
  private async perform(action: () => Promise<void>): Promise<void> {
    this.busy.set(true); this.error.set(''); this.message.set('');
    try { await action(); } catch (error) { this.error.set(String(error)); } finally { this.busy.set(false); }
  }
  async choose(): Promise<void> {
    await this.perform(async () => {
      const path = await this.invoke<string | null>('select_worker_executable');
      if (path) this.form.controls.executable.setValue(path);
    });
  }
  private async persist(): Promise<void> {
    const { password, ...values } = this.form.getRawValue();
    await this.invoke('save_local_worker', { config: { ...values, passwordFile: '' }, password });
    this.form.controls.password.setValue('');
  }
  async save(): Promise<void> { await this.perform(async () => { await this.persist(); await this.refresh(); this.message.set('Einstellungen gespeichert.'); }); }
  async start(): Promise<void> { await this.perform(async () => { await this.persist(); await this.invoke('start_local_worker'); await this.refresh(); }); }
  async stop(): Promise<void> { await this.perform(async () => { await this.invoke('stop_local_worker'); await this.refresh(); }); }
  async dashboard(): Promise<void> {
    await this.perform(async () => { await this.invoke('open_server_dashboard', { address: this.form.controls.serverUrl.value }); });
  }
}
