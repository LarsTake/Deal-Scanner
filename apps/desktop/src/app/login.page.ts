import { Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { AuthService } from './auth.service';

@Component({
  standalone: true,
  imports: [MatButtonModule, MatCardModule, MatFormFieldModule, MatInputModule, ReactiveFormsModule],
  template: `
    <header class="page-header"><div><p class="eyebrow">Identität</p><h1>Anmelden</h1><p>Supabase-JWTs werden lokal validiert; der Desktop speichert die Sitzung im Stronghold-Tresor.</p></div></header>
    <mat-card class="form-card compact">
      @if (!auth.configured()) { <div class="notice error">Supabase-URL und Publishable Key zuerst unter Einstellungen speichern.</div> }
      @if (auth.userEmail()) { <div class="notice">Angemeldet als {{ auth.userEmail() }}</div><button mat-stroked-button (click)="signOut()">Abmelden</button> }
      @else {
        <div class="row actions">
          <button mat-stroked-button type="button" (click)="mode.set('signin')">Anmelden</button>
          <button mat-stroked-button type="button" (click)="mode.set('signup')">Registrieren</button>
        </div>
        <h2>{{ mode() === 'signup' ? 'Account anlegen' : 'Anmelden' }}</h2>
        <form [formGroup]="form" (ngSubmit)="submit()">
          <mat-form-field><mat-label>E-Mail</mat-label><input matInput type="email" formControlName="email" /></mat-form-field>
          <mat-form-field><mat-label>Passwort</mat-label><input matInput type="password" formControlName="password" /></mat-form-field>
          <mat-form-field><mat-label>Desktop-Tresorpassphrase</mat-label><input matInput type="password" formControlName="vaultPassphrase" /><mat-hint>Nur in Tauri erforderlich; wird nicht gespeichert.</mat-hint></mat-form-field>
          @if (error()) { <div class="notice error">{{ error() }}</div> }
          @if (message()) { <div class="notice">{{ message() }}</div> }
          <div class="row actions">
            <button mat-flat-button [disabled]="form.invalid || busy()">
              {{ busy() ? 'Bitte warten …' : mode() === 'signup' ? 'Account anlegen' : 'Anmelden' }}
            </button>
            <button mat-button type="button" [disabled]="!form.controls.email.valid || busy()" (click)="resetPassword()">
              Passwort vergessen
            </button>
          </div>
        </form>
      }
    </mat-card>
  `,
})
export class LoginPage {
  readonly auth = inject(AuthService);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  readonly mode = signal<'signin' | 'signup'>('signin');
  readonly form = new FormGroup({
    email: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.email] }),
    password: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    vaultPassphrase: new FormControl('', { nonNullable: true }),
  });

  async submit(): Promise<void> {
    if (this.form.invalid) return;
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    try {
      const value = this.form.getRawValue();
      if (this.mode() === 'signup') {
        const signedIn = await this.auth.signUp(value.email, value.password, value.vaultPassphrase);
        if (!signedIn) {
          this.message.set('Account angelegt. Bitte bestätige die E-Mail und melde dich danach an.');
          this.mode.set('signin');
        }
      } else {
        await this.auth.signIn(value.email, value.password, value.vaultPassphrase);
      }
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Anmeldung fehlgeschlagen');
    } finally {
      this.busy.set(false);
    }
  }

  async resetPassword(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    try {
      await this.auth.requestPasswordReset(this.form.controls.email.value);
      this.message.set('Die E-Mail zum Zurücksetzen des Passworts wurde versendet.');
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Passwort-Zurücksetzen fehlgeschlagen');
    } finally {
      this.busy.set(false);
    }
  }

  async signOut(): Promise<void> {
    await this.auth.signOut();
  }
}
