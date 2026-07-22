import { DatePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ApiProblemError } from '@deal-scanner/api-client';
import type { FeedbackCreate, ListingSummary } from '@deal-scanner/contracts';

import { ApiService } from './api.service';
import { OfflineCacheService } from './offline-cache.service';

@Component({
  standalone: true,
  imports: [DatePipe, MatButtonModule, MatCardModule, MatChipsModule, MatProgressSpinnerModule, RouterLink],
  template: `
    <header class="page-header"><div><p class="eyebrow">Inventar</p><h1>{{ title }}</h1><p>Deal-Potenzial und Risiko bleiben bewusst zwei getrennte Bewertungen.</p></div></header>
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

  ngOnInit(): void {
    void this.loadMore();
  }

  async loadMore(): Promise<void> {
    this.loading.set(true);
    try {
      const page = await this.api.listings(this.nextCursor() ?? undefined, this.view);
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
