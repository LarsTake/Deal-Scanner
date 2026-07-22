import { Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import type { SearchProfile } from '@deal-scanner/contracts';

import { ApiService } from './api.service';

@Component({
  standalone: true,
  imports: [
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatSlideToggleModule,
    ReactiveFormsModule,
  ],
  template: `
    <header class="page-header"><div><p class="eyebrow">Automatisierung</p><h1>Suchaufträge</h1><p>Jeder Auftrag definiert Kategorie, Preiskorridor und Bewertungsschwellen.</p></div></header>
    @if (error()) { <div class="notice error">{{ error() }}</div> }
    <section class="two-column">
      <mat-card class="form-card">
        <h2>Neuer Suchauftrag</h2>
        <form [formGroup]="form" (ngSubmit)="create()">
          <mat-form-field><mat-label>Name</mat-label><input matInput formControlName="name" /></mat-form-field>
          <mat-form-field><mat-label>Suchbegriff</mat-label><input matInput formControlName="query" /></mat-form-field>
          <mat-form-field><mat-label>Kategorie</mat-label><mat-select formControlName="categoryProfile">
            <mat-option value="computer">Computer</mat-option><mat-option value="simracing">Simracing</mat-option>
            <mat-option value="fpv">FPV & Drohnen</mat-option><mat-option value="general">Allgemein</mat-option>
          </mat-select></mat-form-field>
          <div class="form-row"><mat-form-field><mat-label>Preis min.</mat-label><input matInput type="number" formControlName="minimumPrice" /></mat-form-field><mat-form-field><mat-label>Preis max.</mat-label><input matInput type="number" formControlName="maximumPrice" /></mat-form-field></div>
          <div class="form-row"><mat-form-field><mat-label>Deal mindestens</mat-label><input matInput type="number" formControlName="minimumDealScore" /></mat-form-field><mat-form-field><mat-label>Risiko maximal</mat-label><input matInput type="number" formControlName="maximumRiskScore" /></mat-form-field></div>
          <button mat-flat-button type="submit" [disabled]="form.invalid || saving()">{{ saving() ? 'Speichert…' : 'Suchauftrag speichern' }}</button>
        </form>
      </mat-card>
      <div class="profile-list">
        @for (profile of profiles(); track profile.id) {
          <mat-card><div class="row"><div><h3>{{ profile.name }}</h3><p>{{ profile.query }}</p></div><span class="tag">{{ profile.categoryProfile }}</span></div>
            <small>Deal ≥ {{ profile.minimumDealScore }} · Risiko ≤ {{ profile.maximumRiskScore }} · alle {{ profile.scanIntervalMinutes }} Min.</small>
          </mat-card>
        } @empty { <div class="empty">Noch keine Suchaufträge.</div> }
      </div>
    </section>
  `,
})
export class SearchProfilesPage implements OnInit {
  private readonly api = inject(ApiService);
  readonly profiles = signal<SearchProfile[]>([]);
  readonly saving = signal(false);
  readonly error = signal('');
  readonly form = new FormGroup({
    name: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    query: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    categoryProfile: new FormControl<'computer' | 'simracing' | 'fpv' | 'general'>('computer', { nonNullable: true }),
    minimumPrice: new FormControl<number | null>(null),
    maximumPrice: new FormControl<number | null>(null),
    minimumDealScore: new FormControl(75, { nonNullable: true }),
    maximumRiskScore: new FormControl(45, { nonNullable: true }),
  });

  async ngOnInit(): Promise<void> {
    try { this.profiles.set(await this.api.searchProfiles()); } catch (error) { this.setError(error); }
  }

  async create(): Promise<void> {
    if (this.form.invalid) return;
    this.saving.set(true);
    const value = this.form.getRawValue();
    try {
      const profile = await this.api.createSearchProfile({
        ...value,
        minimumPrice: value.minimumPrice?.toString() ?? null,
        maximumPrice: value.maximumPrice?.toString() ?? null,
        enabledPlatforms: ['ebay'],
        scanIntervalMinutes: 15,
        enabled: true,
      });
      this.profiles.update((profiles) => [...profiles, profile]);
      this.form.patchValue({ name: '', query: '' });
    } catch (error) { this.setError(error); } finally { this.saving.set(false); }
  }

  private setError(error: unknown): void {
    this.error.set(error instanceof Error ? error.message : 'Aktion fehlgeschlagen');
  }
}
