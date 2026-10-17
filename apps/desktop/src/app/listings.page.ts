import { DatePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ApiProblemError, type ListingFilters } from '@deal-scanner/api-client';
import type { FeedbackCreate, ListingSummary } from '@deal-scanner/contracts';

import { ApiService } from './api.service';
import { OfflineCacheService } from './offline-cache.service';

@Component({
  standalone: true,
  imports: [DatePipe, MatButtonModule, MatCardModule, MatChipsModule, MatProgressSpinnerModule, RouterLink,
    ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatSelectModule],
  template: `
    <header class="page-header"><div><p class="eyebrow">Inventar</p><h1>{{ title }}</h1><p>Deal-Potenzial und Risiko bleiben bewusst zwei getrennte Bewertungen.</p></div></header>
    <form [formGroup]="filterForm" (ngSubmit)="applyFilters()" class="form-card">
      <div class="form-row">
        <mat-form-field><mat-label>In Treffern suchen</mat-label><input matInput formControlName="q" /></mat-form-field>
        <mat-form-field><mat-label>Plattformen</mat-label><mat-select formControlName="platforms" multiple>
          <mat-option value="ebay">eBay</mat-option><mat-option value="kleinanzeigen">Kleinanzeigen</mat-option>
          <mat-option value="mydealz">mydealz</mat-option><mat-option value="vinted">Vinted</mat-option>
        </mat-select></mat-form-field>
        <mat-form-field><mat-label>Bewertung</mat-label><mat-select formControlName="assessment">
          <mat-option value="all">Alle Treffer</mat-option><mat-option value="interesting">Interessante Deals</mat-option>
          <mat-option value="suspicious">Auffällige Treffer</mat-option><mat-option value="unknown">Unzureichende Daten</mat-option>
        </mat-select></mat-form-field>
      </div>
      <div class="form-row">
        <mat-form-field><mat-label>Deal mindestens</mat-label><input matInput type="number" min="0" max="100" formControlName="minimumDealScore" placeholder="75" /></mat-form-field>
        <mat-form-field><mat-label>Risiko-Grenze</mat-label><input matInput type="number" min="0" max="100" formControlName="maximumRiskScore" placeholder="45" /></mat-form-field>
        <mat-form-field><mat-label>Datenqualität mindestens</mat-label><input matInput type="number" min="0" max="100" formControlName="minimumDataQuality" placeholder="40" /></mat-form-field>
      </div>
      <p><small>Interessant: Deal ≥ 75, Risiko ≤ 45, Qualität ≥ 40 (falls leer). Auffällig: Risiko über der Grenze. Unklar: Marktwert fehlt oder Qualität zu gering. Keine KI erforderlich.</small></p>
      <div class="row"><button mat-flat-button type="submit" [disabled]="loading()">Filter anwenden</button>
        <button mat-stroked-button type="button" [disabled]="loading()" (click)="resetFilters()">Zurücksetzen</button></div>
    </form>
    @if (loading()) { <mat-spinner diameter="36" /> }
    @if (error()) { <div class="notice error">{{ error() }}</div> }
    <div class="listing-grid wide">
      @for (listing of listings(); track listing.id) {
        <mat-card class="listing-card">
          @if (imageUrls()[listing.id]) { <img class="listing-image" [src]="imageUrls()[listing.id]" [alt]="listing.title" /> }
          <div class="row"><mat-chip>{{ listing.platform }}</mat-chip><span>{{ listing.status }}</span></div>
          <h3><a [routerLink]="['/listings', listing.id]">{{ listing.title }}</a></h3>
          <div class="price">{{ listing.price }} {{ listing.currency }} <small>+ {{ listing.shippingCost }} Versand</small></div>
          @if (listing.analysisStatus === 'COMPLETE' && listing.marketValueMedian == null) {
            <p><small>Analyse verarbeitet · Marktpreis noch nicht belastbar. Passende Vergleichsangebote fehlen.</small></p>
          }
          <div class="score-row">
            <div><small>Deal</small><b class="deal">{{ listing.dealScore ?? '–' }}</b></div>
            <div><small>Risiko</small><b class="risk">{{ listing.riskScore ?? '–' }}</b></div>
            <div><small>Marktwert</small><b>{{ listing.marketValueMedian ?? '–' }} {{ listing.marketValueMedian ? listing.currency : '' }}</b></div>
            <div><small>Datenqualität</small><b>{{ listing.dataQualityScore ?? '–' }}</b></div>
            <div><small>Analyse</small><b>{{ listing.analysisStatus }}</b></div>
          </div>
          <p><small>{{ listing.location ?? 'Ort unbekannt' }} @if (listing.distanceKm) { · {{ listing.distanceKm }} km } · {{ (listing.publishedAt ?? listing.lastSeenAt) | date:'short' }}</small></p>
          @if (products(listing).length) { <mat-chip-set>@for (product of products(listing); track product) { <mat-chip>{{ product }}</mat-chip> }</mat-chip-set> }
          @if (warningText(listing)) { <p class="notice error">{{ warningText(listing) }}</p> }
          <div class="row actions">
            <button mat-stroked-button (click)="feedback(listing, listing.isFavorite ? 'unfavorite' : 'favorite')">
              {{ listing.isFavorite ? 'Favorit entfernen' : 'Favorit' }}
            </button>
            <button mat-stroked-button (click)="feedback(listing, listing.isHidden ? 'unhide' : 'hide')">
              {{ listing.isHidden ? 'Einblenden' : 'Ausblenden' }}
            </button>
            <button mat-stroked-button (click)="feedback(listing, 'goodDeal')">Guter Deal</button>
            <button mat-stroked-button (click)="feedback(listing, 'irrelevant')">Irrelevant</button>
            <button mat-stroked-button (click)="feedback(listing, 'scamConcern')">Bedenken</button>
          </div>
        </mat-card>
      } @empty { @if (!loading()) { <div class="empty">Keine Angebote vorhanden.</div> } }
    </div>
    @if (nextCursor()) { <button mat-stroked-button (click)="loadMore()">Weitere laden</button> }
  `,
  styles: `.listing-image { width: 100%; aspect-ratio: 16 / 9; object-fit: cover; border-radius: 10px; margin-bottom: 12px; }`,
})
export class ListingsPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly offline = inject(OfflineCacheService);
  private readonly route = inject(ActivatedRoute);
  readonly view = (this.route.snapshot.data['view'] ?? 'all') as
    | 'all'
    | 'new'
    | 'favorites'
    | 'hidden';
  readonly title = (this.route.snapshot.data['title'] ?? 'Angebote') as string;
  readonly listings = signal<ListingSummary[]>([]);
  readonly nextCursor = signal<string | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly imageUrls = signal<Record<string, string>>({});
  readonly filterForm = new FormGroup({
    q: new FormControl('', { nonNullable: true }),
    platforms: new FormControl<string[]>([], { nonNullable: true }),
    assessment: new FormControl<NonNullable<ListingFilters['assessment']>>('all', { nonNullable: true }),
    minimumDealScore: new FormControl<number | null>(null),
    maximumRiskScore: new FormControl<number | null>(null),
    minimumDataQuality: new FormControl<number | null>(null),
  });
  private filters: ListingFilters = {};

  ngOnInit(): void {
    const searchProfileId = this.route.snapshot.queryParamMap.get('searchProfileId');
    if (searchProfileId) this.filters = { searchProfileId };
    void this.loadMore();
  }

  async applyFilters(): Promise<void> {
    if (this.loading()) return;
    const value = this.filterForm.getRawValue();
    this.filters = { ...this.filters, q: value.q || undefined,
      platforms: value.platforms.length ? value.platforms : undefined, assessment: value.assessment,
      minimumDealScore: value.minimumDealScore ?? undefined, maximumRiskScore: value.maximumRiskScore ?? undefined,
      minimumDataQuality: value.minimumDataQuality ?? undefined };
    this.listings.set([]);
    for (const url of Object.values(this.imageUrls())) URL.revokeObjectURL(url);
    this.imageUrls.set({});
    this.nextCursor.set(null);
    await this.loadMore();
  }

  async resetFilters(): Promise<void> {
    if (this.loading()) return;
    this.filterForm.reset({ q: '', platforms: [], assessment: 'all', minimumDealScore: null,
      maximumRiskScore: null, minimumDataQuality: null });
    this.filters = {};
    await this.applyFilters();
  }

  async loadMore(): Promise<void> {
    this.loading.set(true);
    try {
      this.error.set('');
      const page = await this.api.listings(this.nextCursor() ?? undefined, this.view, this.filters);
      this.listings.update((items) => [...items, ...page.items]);
      await this.offline.cacheListings(page.items);
      await this.loadImages(page.items);
      this.nextCursor.set(page.nextCursor ?? null);
    } catch (error) {
      const filtered = Object.entries(this.filters).some(([key, value]) => value !== undefined && !(key === 'assessment' && value === 'all'));
      if (!this.nextCursor() && !filtered) {
        const cached = this.filterView(await this.offline.readListings());
        if (cached.length) {
          this.listings.set(cached);
          this.error.set('Offline: zuletzt gespeicherte Angebote werden angezeigt.');
          return;
        }
      }
      this.error.set(error instanceof Error ? error.message : 'Angebote konnten nicht geladen werden');
    } finally {
      this.loading.set(false);
    }
  }

  private filterView(items: ListingSummary[]): ListingSummary[] {
    if (this.view === 'favorites') return items.filter((item) => item.isFavorite && !item.isHidden);
    if (this.view === 'hidden') return items.filter((item) => item.isHidden);
    if (this.view === 'new') return items.filter((item) => item.status === 'NEW' && !item.isHidden);
    return items.filter((item) => !item.isHidden);
  }

  products(listing: ListingSummary): string[] {
    return listing.detectedProducts ?? [];
  }

  warningText(listing: ListingSummary): string {
    return (listing.warnings ?? []).join(' · ');
  }

  private async loadImages(items: ListingSummary[]): Promise<void> {
    await Promise.all(items.map(async (listing) => {
      if (!listing.mainImageId || this.imageUrls()[listing.id]) return;
      try {
        const url = await this.api.imageObjectUrl(listing.mainImageId);
        this.imageUrls.update((current) => ({ ...current, [listing.id]: url }));
      } catch {
        console.warn('Kartenbild nicht verfügbar', listing.id);
      }
    }));
  }

  async feedback(
    listing: ListingSummary,
    feedbackType: FeedbackCreate['feedbackType'],
  ): Promise<void> {
    const payload: FeedbackCreate = {
      feedbackType,
      baseListingVersion: listing.version,
    };
    try {
      const result = await this.api.createFeedback(listing.id, payload);
      this.listings.update((items) =>
        items
          .map((item) =>
            item.id === listing.id
              ? {
                  ...item,
                  version: result.version,
                  isFavorite:
                    feedbackType === 'favorite'
                      ? true
                      : feedbackType === 'unfavorite'
                        ? false
                        : item.isFavorite,
                  isHidden:
                    feedbackType === 'hide'
                      ? true
                      : feedbackType === 'unhide'
                        ? false
                        : item.isHidden,
                }
              : item,
          )
          .filter((item) => {
            if (this.view === 'favorites') return item.isFavorite && !item.isHidden;
            if (this.view === 'hidden') return item.isHidden;
            return !item.isHidden;
          }),
      );
    } catch (error) {
      if (error instanceof ApiProblemError && error.status === 409) {
        this.error.set('Das Angebot wurde geändert. Bitte neu laden und den Konflikt auflösen.');
        return;
      }
      const queued = await this.offline
        .enqueue('feedback', payload, listing.id, listing.version)
        .then(() => true)
        .catch(() => false);
      this.error.set(
        queued
          ? 'Offline: Feedback wurde in der Desktop-Outbox vorgemerkt.'
          : 'Feedback konnte nicht übertragen werden.',
      );
    }
  }
}
