import { Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import type { SearchProfile, SearchProfileCreate } from '@deal-scanner/contracts';

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
        <h2>{{ editingId() ? 'Suchauftrag bearbeiten' : 'Neuer Suchauftrag' }}</h2>
        <form [formGroup]="form" (ngSubmit)="create()">
          <mat-form-field><mat-label>Name</mat-label><input matInput formControlName="name" /></mat-form-field>
          <mat-form-field><mat-label>Suchbegriff</mat-label><input matInput formControlName="query" /></mat-form-field>
          <mat-form-field><mat-label>Kategorie</mat-label><mat-select formControlName="categoryProfile">
            <mat-option value="computer">Computer</mat-option><mat-option value="simracing">Simracing</mat-option>
            <mat-option value="fpv">FPV & Drohnen</mat-option><mat-option value="general">Allgemein</mat-option>
          </mat-select></mat-form-field>
          <div class="form-row"><mat-form-field><mat-label>Preis min.</mat-label><input matInput type="number" formControlName="minimumPrice" /></mat-form-field><mat-form-field><mat-label>Preis max.</mat-label><input matInput type="number" formControlName="maximumPrice" /></mat-form-field></div>
          <div class="form-row"><mat-form-field><mat-label>Standort</mat-label><input matInput formControlName="location" /></mat-form-field><mat-form-field><mat-label>Radius (km)</mat-label><input matInput type="number" formControlName="radiusKm" /></mat-form-field></div>
          <mat-form-field><mat-label>Erforderliche Begriffe (Komma)</mat-label><input matInput formControlName="requiredTerms" /></mat-form-field>
          <mat-form-field><mat-label>Ausgeschlossene Begriffe (Komma)</mat-label><input matInput formControlName="excludedTerms" /></mat-form-field>
          <mat-form-field><mat-label>Erforderliche Produkte (Komma)</mat-label><input matInput formControlName="requiredProducts" /></mat-form-field>
          <mat-form-field><mat-label>Ausgeschlossene Produkte (Komma)</mat-label><input matInput formControlName="excludedProducts" /></mat-form-field>
          <div class="form-row"><mat-form-field><mat-label>Deal mindestens</mat-label><input matInput type="number" formControlName="minimumDealScore" /></mat-form-field><mat-form-field><mat-label>Risiko maximal</mat-label><input matInput type="number" formControlName="maximumRiskScore" /></mat-form-field></div>
          <div class="form-row"><mat-form-field><mat-label>Marktvorteil mindestens (%)</mat-label><input matInput type="number" formControlName="minimumMarketAdvantagePercent" /></mat-form-field><mat-form-field><mat-label>Anzeige maximal (Stunden)</mat-label><input matInput type="number" formControlName="maximumListingAgeHours" /></mat-form-field></div>
          <div class="row"><mat-slide-toggle formControlName="desktopEnabled">Desktop</mat-slide-toggle><mat-slide-toggle formControlName="ntfyEnabled">ntfy</mat-slide-toggle></div>
          <button mat-flat-button type="submit" [disabled]="form.invalid || saving()">{{ saving() ? 'Speichert…' : 'Suchauftrag speichern' }}</button>
          @if (editingId()) { <button mat-stroked-button type="button" (click)="cancelEdit()">Abbrechen</button> }
        </form>
      </mat-card>
      <div class="profile-list">
        @for (profile of profiles(); track profile.id) {
          <mat-card><div class="row"><div><h3>{{ profile.name }}</h3><p>{{ profile.query }}</p></div><span class="tag">{{ profile.categoryProfile }}</span></div>
            <small>Deal ≥ {{ profile.minimumDealScore }} · Risiko ≤ {{ profile.maximumRiskScore }} · alle {{ profile.scanIntervalMinutes }} Min.</small>
            <p>{{ profile.location ?? 'ohne Ortsfilter' }}{{ profile.radiusKm ? ' · ' + profile.radiusKm + ' km' : '' }}</p>
            <div class="row actions">
              <button mat-stroked-button (click)="edit(profile)">Bearbeiten</button>
              <button mat-stroked-button (click)="toggle(profile)">{{ profile.enabled ? 'Pausieren' : 'Fortsetzen' }}</button>
              <button mat-stroked-button (click)="remove(profile)">Löschen</button>
            </div>
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
  readonly editingId = signal<string | null>(null);
  readonly form = new FormGroup({
    name: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    query: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    categoryProfile: new FormControl<'computer' | 'simracing' | 'fpv' | 'general'>('computer', { nonNullable: true }),
    minimumPrice: new FormControl<number | null>(null),
    maximumPrice: new FormControl<number | null>(null),
    location: new FormControl('', { nonNullable: true }),
    radiusKm: new FormControl<number | null>(null),
    requiredTerms: new FormControl('', { nonNullable: true }),
    excludedTerms: new FormControl('', { nonNullable: true }),
    requiredProducts: new FormControl('', { nonNullable: true }),
    excludedProducts: new FormControl('', { nonNullable: true }),
    minimumDealScore: new FormControl(75, { nonNullable: true }),
    maximumRiskScore: new FormControl(45, { nonNullable: true }),
    minimumMarketAdvantagePercent: new FormControl(15, { nonNullable: true }),
    maximumListingAgeHours: new FormControl<number | null>(24),
    desktopEnabled: new FormControl(true, { nonNullable: true }),
    ntfyEnabled: new FormControl(false, { nonNullable: true }),
  });

  async ngOnInit(): Promise<void> {
    try { this.profiles.set(await this.api.searchProfiles()); } catch (error) { this.setError(error); }
  }

  async create(): Promise<void> {
    if (this.form.invalid) return;
    this.saving.set(true);
    const value = this.form.getRawValue();
    try {
      const split = (input: string) => input.split(',').map((item) => item.trim()).filter(Boolean);
      const payload: SearchProfileCreate = {
        name: value.name,
        query: value.query,
        categoryProfile: value.categoryProfile,
        minimumPrice: value.minimumPrice?.toString() ?? null,
        maximumPrice: value.maximumPrice?.toString() ?? null,
        location: value.location || null,
        radiusKm: value.radiusKm,
        requiredTerms: split(value.requiredTerms),
        excludedTerms: split(value.excludedTerms),
        requiredProducts: split(value.requiredProducts),
        excludedProducts: split(value.excludedProducts),
        minimumDealScore: value.minimumDealScore,
        maximumRiskScore: value.maximumRiskScore,
        notificationSettings: {
          minimumMarketAdvantagePercent: value.minimumMarketAdvantagePercent.toString(),
          maximumListingAgeHours: value.maximumListingAgeHours,
          desktopEnabled: value.desktopEnabled,
          ntfyEnabled: value.ntfyEnabled,
        },
        enabledPlatforms: ['ebay'],
        scanIntervalMinutes: 15,
        enabled: true,
      };
      const editingId = this.editingId();
      const profile = editingId
        ? await this.api.updateSearchProfile(editingId, payload)
        : await this.api.createSearchProfile(payload);
      this.profiles.update((profiles) => editingId
        ? profiles.map((item) => item.id === profile.id ? profile : item)
        : [...profiles, profile]);
      this.editingId.set(null);
      this.form.patchValue({ name: '', query: '' });
    } catch (error) { this.setError(error); } finally { this.saving.set(false); }
  }

  edit(profile: SearchProfile): void {
    this.editingId.set(profile.id);
    const notificationSettings: NonNullable<SearchProfile['notificationSettings']> = profile.notificationSettings ?? {
      minimumMarketAdvantagePercent: '15',
      maximumListingAgeHours: 24,
      desktopEnabled: true,
      ntfyEnabled: false,
    };
    this.form.patchValue({
      name: profile.name,
      query: profile.query,
      categoryProfile: profile.categoryProfile,
      minimumPrice: profile.minimumPrice === null ? null : Number(profile.minimumPrice),
      maximumPrice: profile.maximumPrice === null ? null : Number(profile.maximumPrice),
      location: profile.location ?? '',
      radiusKm: profile.radiusKm,
      requiredTerms: (profile.requiredTerms ?? []).join(', '),
      excludedTerms: (profile.excludedTerms ?? []).join(', '),
      requiredProducts: (profile.requiredProducts ?? []).join(', '),
      excludedProducts: (profile.excludedProducts ?? []).join(', '),
      minimumDealScore: profile.minimumDealScore,
      maximumRiskScore: profile.maximumRiskScore,
      minimumMarketAdvantagePercent: Number(notificationSettings.minimumMarketAdvantagePercent ?? 15),
      maximumListingAgeHours: notificationSettings.maximumListingAgeHours ?? 24,
      desktopEnabled: notificationSettings.desktopEnabled ?? true,
      ntfyEnabled: notificationSettings.ntfyEnabled ?? false,
    });
  }

  cancelEdit(): void {
    this.editingId.set(null);
    this.form.reset({
      name: '', query: '', categoryProfile: 'computer', minimumPrice: null, maximumPrice: null,
      location: '', radiusKm: null, requiredTerms: '', excludedTerms: '', requiredProducts: '',
      excludedProducts: '', minimumDealScore: 75, maximumRiskScore: 45,
      minimumMarketAdvantagePercent: 15, maximumListingAgeHours: 24,
      desktopEnabled: true, ntfyEnabled: false,
    });
  }

  async toggle(profile: SearchProfile): Promise<void> {
    try {
      const updated = await this.api.updateSearchProfile(profile.id, this.editable(profile, !profile.enabled));
      this.profiles.update((profiles) => profiles.map((item) => item.id === updated.id ? updated : item));
    } catch (error) { this.setError(error); }
  }

  async remove(profile: SearchProfile): Promise<void> {
    try {
      await this.api.deleteSearchProfile(profile.id);
      this.profiles.update((profiles) => profiles.filter((item) => item.id !== profile.id));
    } catch (error) { this.setError(error); }
  }

  private editable(profile: SearchProfile, enabled: boolean): SearchProfileCreate {
    return {
      name: profile.name,
      query: profile.query,
      categoryProfile: profile.categoryProfile,
      minimumPrice: profile.minimumPrice,
      maximumPrice: profile.maximumPrice,
      location: profile.location,
      radiusKm: profile.radiusKm,
      requiredTerms: profile.requiredTerms,
      excludedTerms: profile.excludedTerms,
      requiredProducts: profile.requiredProducts,
      excludedProducts: profile.excludedProducts,
      minimumDealScore: profile.minimumDealScore,
      maximumRiskScore: profile.maximumRiskScore,
      notificationSettings: profile.notificationSettings,
      enabledPlatforms: profile.enabledPlatforms,
      scanIntervalMinutes: profile.scanIntervalMinutes,
      enabled,
    };
  }

  private setError(error: unknown): void {
    this.error.set(error instanceof Error ? error.message : 'Aktion fehlgeschlagen');
  }
}
