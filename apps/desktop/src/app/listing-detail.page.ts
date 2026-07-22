import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ActivatedRoute } from '@angular/router';
import type { FeedbackCreate, ListingDetail, ListingImage } from '@deal-scanner/contracts';

import { ApiService } from './api.service';

@Component({
  standalone: true,
  imports: [MatButtonModule, MatCardModule, MatChipsModule, MatProgressSpinnerModule],
  template: `
    @if (loading()) { <mat-spinner diameter="36" /> }
    @if (error()) { <div class="notice error">{{ error() }}</div> }
    @if (listing(); as item) {
      <header class="page-header">
        <div>
          <p class="eyebrow">{{ item.platform }} · {{ item.categoryProfile }}</p>
          <h1>{{ item.title }}</h1>
          <p>{{ item.location ?? 'Ort nicht angegeben' }} · Version {{ item.version }}</p>
        </div>
        <a mat-flat-button [href]="item.url" target="_blank" rel="noopener noreferrer">Original öffnen</a>
      </header>
      <section class="metric-grid">
        <mat-card><span>Preis</span><strong>{{ item.price }} {{ item.currency }}</strong><small>+ {{ item.shippingCost }} Versand</small></mat-card>
        <mat-card><span>Deal</span><strong class="deal">{{ item.dealScore ?? '–' }}</strong><small>ohne Risikoverrechnung</small></mat-card>
        <mat-card><span>Risiko</span><strong class="risk">{{ item.riskScore ?? '–' }}</strong><small>evidenzbasiert</small></mat-card>
        <mat-card><span>Analyse</span><strong>{{ item.analysisStatus }}</strong><small>{{ item.status }}</small></mat-card>
      </section>
      <mat-card class="form-card">
        <h2>Beschreibung</h2>
        <p class="description">{{ item.description || 'Keine Beschreibung vorhanden.' }}</p>
        <div class="row actions">
          <button mat-stroked-button (click)="toggleFavorite(item)">{{ item.isFavorite ? 'Favorit entfernen' : 'Als Favorit speichern' }}</button>
          <button mat-stroked-button (click)="toggleHidden(item)">{{ item.isHidden ? 'Wieder einblenden' : 'Ausblenden' }}</button>
          <button mat-stroked-button (click)="reanalyze()">Neu analysieren</button>
          <button mat-flat-button (click)="evaluate()">Neu bewerten</button>
        </div>
      </mat-card>
      <section class="section-head"><div><p class="eyebrow">Medien</p><h2>Bilder und OCR</h2></div></section>
      <div class="listing-grid">
        @for (image of images(); track image.id) {
          <mat-card class="listing-card">
            @if (imageUrls()[image.id]; as url) { <img class="listing-image" [src]="url" [alt]="item.title" /> }
            <div class="row"><mat-chip>{{ image.analysisStatus }}</mat-chip><span>{{ image.width }} × {{ image.height }}</span></div>
            <small>SHA-256 {{ image.sha256Hash.slice(0, 12) }}… · pHash {{ image.perceptualHash }}</small>
          </mat-card>
        } @empty { <div class="empty">Keine Bilder importiert.</div> }
      </div>
      <section class="section-head"><div><p class="eyebrow">Nachvollziehbarkeit</p><h2>Risikosignale</h2></div></section>
      <div class="listing-grid">
        @for (signal of item.riskSignals; track signal.type + signal.evidence) {
          <mat-card class="listing-card">
            <div class="row"><mat-chip>{{ signal.positive ? 'positiv' : 'Warnung' }}</mat-chip><b>{{ signal.severity }}</b></div>
            <h3>{{ signal.type }}</h3>
            <p>{{ signal.evidence }}</p>
            <small>{{ signal.source }} · Konfidenz {{ signal.confidence }}</small>
          </mat-card>
        } @empty { <div class="empty">Keine Risikosignale erkannt.</div> }
      </div>
    }
  `,
  styles: `.description { white-space: pre-wrap; line-height: 1.65; } .listing-image { width: 100%; aspect-ratio: 16 / 10; object-fit: contain; border-radius: 10px; background: #07120f; margin-bottom: 14px; }`,
})
export class ListingDetailPage implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly id = inject(ActivatedRoute).snapshot.paramMap.get('id') ?? '';
  readonly listing = signal<ListingDetail | null>(null);
  readonly images = signal<ListingImage[]>([]);
  readonly imageUrls = signal<Record<string, string>>({});
  readonly loading = signal(false);
  readonly error = signal('');

  async ngOnInit(): Promise<void> {
    await this.reload();
  }

  ngOnDestroy(): void {
    for (const url of Object.values(this.imageUrls())) URL.revokeObjectURL(url);
  }

  async evaluate(): Promise<void> {
    await this.run(() => this.api.evaluateListing(this.id));
  }

  async reanalyze(): Promise<void> {
    await this.run(() => this.api.reanalyzeListing(this.id));
  }

  async toggleFavorite(item: ListingDetail): Promise<void> {
    await this.feedback(item, item.isFavorite ? 'unfavorite' : 'favorite');
  }

  async toggleHidden(item: ListingDetail): Promise<void> {
    await this.feedback(item, item.isHidden ? 'unhide' : 'hide');
  }

  private async feedback(item: ListingDetail, feedbackType: FeedbackCreate['feedbackType']): Promise<void> {
    await this.run(() =>
      this.api.createFeedback(item.id, { feedbackType, baseListingVersion: item.version }),
    );
  }

  private async run(operation: () => Promise<unknown>): Promise<void> {
    this.error.set('');
    try {
      await operation();
      await this.reload();
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Aktion fehlgeschlagen');
    }
  }

  private async reload(): Promise<void> {
    this.loading.set(true);
    try {
      const [listing, images] = await Promise.all([
        this.api.listing(this.id),
        this.api.listingImages(this.id),
      ]);
      this.listing.set(listing);
      this.images.set(images);
      for (const url of Object.values(this.imageUrls())) URL.revokeObjectURL(url);
      const imageUrls: Record<string, string> = {};
      await Promise.all(
        images.map(async (image) => {
          try {
            imageUrls[image.id] = await this.api.imageObjectUrl(image.id);
          } catch {
            // Metadata remains visible when the binary is temporarily unavailable.
          }
        }),
      );
      this.imageUrls.set(imageUrls);
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Angebot konnte nicht geladen werden');
    } finally {
      this.loading.set(false);
    }
  }
}
