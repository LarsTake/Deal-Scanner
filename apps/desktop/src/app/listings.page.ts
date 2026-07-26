import { DatePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ApiProblemError } from '@deal-scanner/api-client';
import type { FeedbackCreate, ListingSummary } from '@deal-scanner/contracts';

import { ApiService } from './api.service';
import { OfflineCacheService } from './offline-cache.service';

@Component({
  standalone: true,
  imports: [
    DatePipe,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    RouterLink,
  ],
  template: `
    <header class="page-header"><div><p class="eyebrow">Inventar</p><h1>{{ title }}</h1><p>Deal-Potenzial und Risiko bleiben bewusst zwei getrennte Bewertungen.</p></div></header>
    <nav class="view-tab-bar">
      <a mat-stroked-button routerLink="/listings" [class.active-tab]="view === 'all'">Alle Angebote</a>
      <a mat-stroked-button routerLink="/top-rated" [class.active-tab]="view === 'top_rated'">⭐ Beste Angebote</a>
      <a mat-stroked-button routerLink="/new-listings" [class.active-tab]="view === 'new'">Neue Angebote</a>
      <a mat-stroked-button routerLink="/favorites" [class.active-tab]="view === 'favorites'">Favoriten</a>
      <a mat-stroked-button routerLink="/hidden" [class.active-tab]="view === 'hidden'">Ausgeblendete Angebote</a>
    </nav>
    <div class="filter-bar">
      <mat-form-field appearance="outline" class="filter-field">
        <mat-label>Plattform</mat-label>
        <mat-select [ngModel]="selectedPlatform()" (ngModelChange)="onPlatformChange($event)">
          <mat-option value="all">Alle Plattformen</mat-option>
          <mat-option value="ebay">eBay</mat-option>
          <mat-option value="kleinanzeigen">Kleinanzeigen</mat-option>
          <mat-option value="manual">Manuell importiert</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" class="filter-field">
        <mat-label>Kategorie</mat-label>
        <mat-select [ngModel]="selectedCategory()" (ngModelChange)="onCategoryChange($event)">
          <mat-option value="all">Alle Kategorien</mat-option>
          <mat-option value="computer">Computer & PCs</mat-option>
          <mat-option value="simracing">Simracing</mat-option>
          <mat-option value="fpv">FPV & Drohnen</mat-option>
          <mat-option value="real_estate">Immobilien</mat-option>
          <mat-option value="vehicles">Fahrzeuge</mat-option>
          <mat-option value="electronics">Elektronik</mat-option>
          <mat-option value="general">Allgemein</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" class="filter-field search-input">
        <mat-label>Suchbegriff (z.B. PC, i7, Gebraucht...)</mat-label>
        <input matInput [ngModel]="searchQuery()" (ngModelChange)="onSearchQueryChange($event)" placeholder="Produkte oder Titel durchsuchen..." />
      </mat-form-field>
      <mat-form-field appearance="outline" class="filter-field">
        <mat-label>Importiert ab</mat-label>
        <input matInput type="date" [ngModel]="importedFrom()" (ngModelChange)="onImportedFromChange($event)" />
      </mat-form-field>
      <mat-form-field appearance="outline" class="filter-field">
        <mat-label>Importiert bis</mat-label>
        <input matInput type="date" [ngModel]="importedTo()" (ngModelChange)="onImportedToChange($event)" />
      </mat-form-field>
      <div class="preset-buttons">
        <button mat-stroked-button color="accent" (click)="applyUsedPcsPreset('ebay')">🖥️ Nur gebrauchte PCs (eBay)</button>
        <button mat-stroked-button (click)="applyUsedPcsPreset('all')">🖥️ Gebrauchte PCs (Alle)</button>
        <button mat-button (click)="resetFilters()">Filter zurücksetzen</button>
      </div>
    </div>
    @if (loading()) { <mat-spinner diameter="36" /> }
    @if (error()) { <div class="notice error">{{ error() }}</div> }
    <div class="listing-grid wide">
      @for (listing of listings(); track listing.id) {
        <mat-card class="listing-card">
          @if (imageUrls()[listing.id]) { <img class="listing-image" [src]="imageUrls()[listing.id]" [alt]="listing.title" /> }
          <div class="row"><mat-chip>{{ listing.platform }}</mat-chip><span>{{ listing.status }}</span></div>
          <h3><a [routerLink]="['/listings', listing.id]">{{ listing.title }}</a></h3>
          <div class="price">{{ listing.price }} {{ listing.currency }} <small>+ {{ listing.shippingCost }} Versand</small></div>
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
  styles: `
    .view-tab-bar { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
    .view-tab-bar a.active-tab { background: color-mix(in srgb, var(--accent) 20%, transparent); color: var(--accent); border-color: var(--accent); font-weight: 600; }
    .filter-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 24px; padding: 14px 18px; background: color-mix(in srgb, var(--surface) 90%, transparent); border: 1px solid var(--line); border-radius: 12px; }
    .filter-field { margin-bottom: -1.25em; }
    .search-input { min-width: 260px; flex: 1; }
    .preset-buttons { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .listing-image { width: 100%; aspect-ratio: 16 / 9; object-fit: cover; border-radius: 10px; margin-bottom: 12px; }
  `,
})
export class ListingsPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly offline = inject(OfflineCacheService);
  private readonly route = inject(ActivatedRoute);
  readonly view = (this.route.snapshot.data['view'] ?? 'all') as
    | 'all'
    | 'new'
    | 'favorites'
    | 'hidden'
    | 'top_rated';
  readonly title = (this.route.snapshot.data['title'] ?? 'Angebote') as string;
  readonly listings = signal<ListingSummary[]>([]);
  readonly nextCursor = signal<string | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly imageUrls = signal<Record<string, string>>({});
  readonly selectedPlatform = signal<string>('all');
  readonly selectedCategory = signal<string>('all');
  readonly searchQuery = signal<string>('');
  readonly importedFrom = signal<string>('');
  readonly importedTo = signal<string>('');

  ngOnInit(): void {
    void this.reloadListings();
  }

  onPlatformChange(value: string): void {
    this.selectedPlatform.set(value);
    void this.reloadListings();
  }

  onCategoryChange(value: string): void {
    this.selectedCategory.set(value);
    void this.reloadListings();
  }

  onSearchQueryChange(value: string): void {
    this.searchQuery.set(value);
    void this.reloadListings();
  }

  onImportedFromChange(value: string): void {
    this.importedFrom.set(value);
    void this.reloadListings();
  }

  onImportedToChange(value: string): void {
    this.importedTo.set(value);
    void this.reloadListings();
  }

  applyUsedPcsPreset(platform: 'ebay' | 'all'): void {
    this.selectedPlatform.set(platform);
    this.selectedCategory.set('computer');
    this.searchQuery.set('PC');
    void this.reloadListings();
  }

  resetFilters(): void {
    this.selectedPlatform.set('all');
    this.selectedCategory.set('all');
    this.searchQuery.set('');
    this.importedFrom.set('');
    this.importedTo.set('');
    void this.reloadListings();
  }

  async reloadListings(): Promise<void> {
    this.listings.set([]);
    this.nextCursor.set(null);
    await this.loadMore();
  }

  async loadMore(): Promise<void> {
    this.loading.set(true);
    try {
      const page = await this.api.listings(
        this.nextCursor() ?? undefined,
        this.view,
        this.selectedPlatform() !== 'all' ? this.selectedPlatform() : undefined,
        this.selectedCategory() !== 'all' ? this.selectedCategory() : undefined,
        this.searchQuery().trim() || undefined,
        this.importedFrom() ? new Date(`${this.importedFrom()}T00:00:00`).toISOString() : undefined,
        this.importedTo() ? new Date(`${this.importedTo()}T23:59:59.999`).toISOString() : undefined,
      );
      this.listings.update((items) => [...items, ...page.items]);
      await this.offline.cacheListings(page.items);
      await this.loadImages(page.items);
      this.nextCursor.set(page.nextCursor ?? null);
    } catch (error) {
      if (!this.nextCursor()) {
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
    let result = items;
    if (this.view === 'favorites') result = result.filter((item) => item.isFavorite && !item.isHidden);
    else if (this.view === 'hidden') result = result.filter((item) => item.isHidden);
    else if (this.view === 'new') result = result.filter((item) => item.status === 'NEW' && !item.isHidden);
    else if (this.view === 'top_rated')
      result = result
        .filter((item) => !item.isHidden && typeof item.dealScore === 'number' && item.dealScore >= 70)
        .sort((a, b) => (b.dealScore ?? 0) - (a.dealScore ?? 0));
    else result = result.filter((item) => !item.isHidden);

    const platform = this.selectedPlatform();
    if (platform && platform !== 'all') {
      result = result.filter((item) => item.platform.toLowerCase().includes(platform.toLowerCase()));
    }

    const query = this.searchQuery().trim().toLowerCase();
    if (query) {
      result = result.filter(
        (item) =>
          item.title.toLowerCase().includes(query) ||
          (item.detectedProducts ?? []).some((p) => p.toLowerCase().includes(query)),
      );
    }
    return result;
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
