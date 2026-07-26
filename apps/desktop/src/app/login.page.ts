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
      @if (auth.redirectError()) {
        <div class="notice error">{{ auth.redirectError() }} Bitte fordere einen neuen Passwort-Link an.</div>
      }
      @if (auth.passwordRecovery()) {
        <h2>Neues Passwort festlegen</h2>
        <p>Der Recovery-Link wurde bestätigt. Lege jetzt dein neues Passwort fest.</p>
        <form [formGroup]="recoveryForm" (ngSubmit)="completePasswordReset()">
          <mat-form-field>
            <mat-label>Neues Passwort</mat-label>
            <input matInput type="password" autocomplete="new-password" formControlName="password" />
            <mat-hint>Mindestens 8 Zeichen</mat-hint>
          </mat-form-field>
          <mat-form-field>
            <mat-label>Passwort wiederholen</mat-label>
            <input matInput type="password" autocomplete="new-password" formControlName="confirmation" />
          </mat-form-field>
          @if (error()) { <div class="notice error">{{ error() }}</div> }
          <button mat-flat-button [disabled]="recoveryForm.invalid || busy()">
            {{ busy() ? 'Passwort wird gespeichert …' : 'Neues Passwort speichern' }}
          </button>
        </form>
      }
      @else if (auth.userEmail()) { <div class="notice">Angemeldet als {{ auth.userEmail() }}</div><button mat-stroked-button (click)="signOut()">Abmelden</button> }
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
            @if (mode() === 'signin') {
              <button
                mat-stroked-button
                type="button"
                [disabled]="!form.controls.vaultPassphrase.value || busy()"
                (click)="unlockSavedSession()"
              >
                Gespeicherte Sitzung entsperren
              </button>
            }
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
  readonly recoveryForm = new FormGroup({
    password: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.minLength(8)],
    }),
    confirmation: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.minLength(8)],
    }),
  });
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

  async completePasswordReset(): Promise<void> {
    if (this.recoveryForm.invalid) return;
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    try {
      const { password, confirmation } = this.recoveryForm.getRawValue();
      if (password !== confirmation) {
        this.error.set('Die beiden Passwörter stimmen nicht überein.');
        return;
      }
      await this.auth.updatePassword(password);
      this.recoveryForm.reset();
      this.message.set('Passwort geändert. Du kannst dich jetzt mit dem neuen Passwort anmelden.');
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Passwort konnte nicht gespeichert werden');
    } finally {
      this.busy.set(false);
    }
  }

  async unlockSavedSession(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    try {
      const unlocked = await this.auth.unlockDesktop(this.form.controls.vaultPassphrase.value);
      if (!unlocked) {
        this.error.set('Im Desktop-Tresor wurde keine gespeicherte Sitzung gefunden.');
      }
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Desktop-Tresor konnte nicht entsperrt werden');
    } finally {
      this.busy.set(false);
    }
  }

  async signOut(): Promise<void> {
    await this.auth.signOut();
  }
}
