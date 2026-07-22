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
    <header class="page-header"><div><p class="eyebrow">Konfiguration</p><h1>Einstellungen</h1><p>Publishable Supabase-Daten sind keine Service-Secrets. Änderungen der API-URL greifen nach einem Neustart.</p></div></header>
    <mat-card class="form-card compact"><form [formGroup]="form" (ngSubmit)="save()">
      <mat-form-field><mat-label>API-URL</mat-label><input matInput formControlName="apiUrl" /></mat-form-field>
      <mat-form-field><mat-label>Supabase-URL</mat-label><input matInput formControlName="supabaseUrl" /></mat-form-field>
      <mat-form-field><mat-label>Supabase Publishable Key</mat-label><input matInput type="password" formControlName="supabaseKey" /></mat-form-field>
      <button mat-flat-button [disabled]="form.invalid">Speichern</button>
      @if (saved()) { <span class="notice">Gespeichert.</span> }
    </form></mat-card>
  `,
})
export class SettingsPage {
  private readonly auth = inject(AuthService);
  readonly saved = signal(false);
  readonly form = new FormGroup({
    apiUrl: new FormControl(localStorage.getItem('deal-scanner-api-url') ?? 'http://127.0.0.1:8000', { nonNullable: true, validators: [Validators.required] }),
    supabaseUrl: new FormControl(localStorage.getItem('deal-scanner-supabase-url') ?? '', { nonNullable: true }),
    supabaseKey: new FormControl(localStorage.getItem('deal-scanner-supabase-key') ?? '', { nonNullable: true }),
  });
  save(): void {
    const value = this.form.getRawValue();
    localStorage.setItem('deal-scanner-api-url', value.apiUrl.replace(/\/$/, ''));
    if (value.supabaseUrl && value.supabaseKey) this.auth.configure(value.supabaseUrl, value.supabaseKey);
    this.saved.set(true);
  }
}
