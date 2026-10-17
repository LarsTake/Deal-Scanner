import { Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { AuthService } from './auth.service';
import { defaultApiUrl } from './connection-target';

function savedServerUrl(): string {
  try {
    const addresses: unknown = JSON.parse(localStorage.getItem('deal-scanner-server-addresses') ?? '[]');
    if (Array.isArray(addresses)) {
      const saved = addresses.filter((address): address is string => typeof address === 'string').join('\n');
      if (saved) return saved;
    }
  } catch { /* Fall back to the last selected server if the saved list is damaged. */ }
  return localStorage.getItem('deal-scanner-api-url') || defaultApiUrl(window.location, '__TAURI_INTERNALS__' in window);
}

@Component({
  standalone: true,
  imports: [MatButtonModule, MatCardModule, MatFormFieldModule, MatInputModule, ReactiveFormsModule],
  template: `
    <header class="page-header"><div><p class="eyebrow">Identität</p><h1>Anmelden</h1><p>Supabase-JWTs werden lokal validiert; der Desktop speichert die Sitzung im Stronghold-Tresor.</p></div></header>
    <mat-card class="form-card compact">
      <h2>Scanner-Server</h2>
      <p>Die App lädt die Supabase-Konfiguration automatisch vom Server. Du benötigst hier keine Supabase-URL und keinen Schlüssel.</p>
      <mat-form-field><mat-label>Scanner-Server</mat-label><input matInput [formControl]="serverUrl" placeholder="https://scanner.example.com" /></mat-form-field>
      <button mat-stroked-button type="button" (click)="connectServer()" [disabled]="busy()">Server verbinden</button>
      <p class="notice">{{ auth.connectionMessage() }}</p>
      @if (auth.userEmail()) { <div class="notice">Angemeldet als {{ auth.userEmail() }}</div><button mat-stroked-button (click)="signOut()">Abmelden</button> }
      @else {
        <form [formGroup]="form" (ngSubmit)="signIn()">
          <mat-form-field><mat-label>E-Mail</mat-label><input matInput type="email" formControlName="email" /></mat-form-field>
          <mat-form-field><mat-label>Passwort</mat-label><input matInput type="password" formControlName="password" /></mat-form-field>
          <mat-form-field><mat-label>Desktop-Tresorpassphrase</mat-label><input matInput type="password" formControlName="vaultPassphrase" /><mat-hint>Nur in Tauri erforderlich; wird nicht gespeichert.</mat-hint></mat-form-field>
          @if (error()) { <div class="notice error">{{ error() }}</div> }
          <button mat-flat-button [disabled]="form.invalid || busy()">{{ busy() ? 'Anmeldung…' : 'Anmelden' }}</button>
        </form>
      }
    </mat-card>
  `,
})
export class LoginPage {
  readonly auth = inject(AuthService);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly serverUrl = new FormControl(savedServerUrl(), { nonNullable: true });
  readonly form = new FormGroup({
    email: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.email] }),
    password: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    vaultPassphrase: new FormControl('', { nonNullable: true }),
  });

  async signIn(): Promise<void> {
    if (this.form.invalid) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const value = this.form.getRawValue();
      await this.auth.signIn(value.email, value.password, value.vaultPassphrase);
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Anmeldung fehlgeschlagen');
    } finally {
      this.busy.set(false);
    }
  }

  async connectServer(): Promise<void> {
    this.busy.set(true); this.error.set('');
    try {
      await this.auth.connectToServer(this.serverUrl.value);
      window.location.reload();
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Serververbindung fehlgeschlagen');
    } finally { this.busy.set(false); }
  }

  async signOut(): Promise<void> {
    await this.auth.signOut();
  }
}
