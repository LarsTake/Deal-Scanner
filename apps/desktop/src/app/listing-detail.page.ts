import { JsonPipe } from '@angular/common';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ActivatedRoute } from '@angular/router';
import type { FeedbackCreate, ListingDetail, ListingImage } from '@deal-scanner/contracts';

import { ApiService } from './api.service';

@Component({
  standalone: true,
  imports: [
    JsonPipe,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    ReactiveFormsModule,
  ],
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
        @if (item.seller; as seller) {
          <h3>Verkäufer</h3>
          <p>{{ seller.displayName ?? seller.externalId }} · {{ seller.location ?? 'Ort unbekannt' }}</p>
          <small>{{ seller.accountAgeText ?? 'Accountalter unbekannt' }} · {{ seller.ratingText ?? 'Keine sichtbare Bewertung' }} · {{ seller.reviewCount ?? '–' }} Bewertungen</small>
        } @else {
          <p><small>Keine Verkäuferdaten verfügbar – dies erhöht den Risiko-Score nicht automatisch.</small></p>
        }
        <div class="row actions">
          <button mat-stroked-button (click)="toggleFavorite(item)">{{ item.isFavorite ? 'Favorit entfernen' : 'Als Favorit speichern' }}</button>
          <button mat-stroked-button (click)="toggleHidden(item)">{{ item.isHidden ? 'Wieder einblenden' : 'Ausblenden' }}</button>
          <button mat-stroked-button (click)="reanalyze()">KI-Tiefenanalyse anfordern</button>
          <button mat-flat-button (click)="evaluate()">Neu bewerten</button>
        </div>
      </mat-card>
      <section class="section-head"><div><p class="eyebrow">Beobachtungen</p><h2>Preisverlauf und Auffälligkeiten</h2></div></section>
      <p><small>Sachliche Hinweise, getrennt vom Risiko-Score. Keine zusätzlichen Push-Meldungen.</small></p>
      <div class="listing-grid">
        @for (finding of item.findings; track finding.id) {
          <mat-card class="listing-card">
            <h3>{{ finding.title }}</h3><p>{{ finding.description }}</p>
            <small>{{ finding.observedAt }} · {{ finding.source }}</small>
            <details><summary>Belege und Grenzwerte</summary><pre>{{ finding.evidence | json }}</pre></details>
          </mat-card>
        } @empty { <div class="empty">Keine entsprechenden Beobachtungen vorhanden. Das bestätigt weder Sicherheit noch Vollständigkeit.</div> }
      </div>
      <section class="section-head"><div><p class="eyebrow">Struktur</p><h2>Erkannte Produkte und Attribute</h2></div></section>
      <div class="listing-grid">
        @for (product of item.products; track product.id) {
          <mat-card class="listing-card">
            <div class="row"><mat-chip>{{ product.productType }}</mat-chip><span>{{ product.detectionSource }}</span></div>
            <h3>{{ product.manufacturer ?? '' }} {{ product.model }} {{ product.variant ?? '' }}</h3>
            <p>{{ product.evidence }}</p>
            <small>Menge {{ product.quantity }} · Konfidenz {{ product.confidence }}</small>
            @for (attribute of product.attributes; track attribute.id) {
              <p><b>{{ attribute.attributeKey }}:</b> {{ attribute.value }} {{ attribute.unit ?? '' }}</p>
            }
          </mat-card>
        } @empty { <div class="empty">Noch keine Produkte erkannt.</div> }
      </div>
      <mat-card class="form-card">
        <h2>Produkterkennung korrigieren</h2>
        <form [formGroup]="correctionForm" (ngSubmit)="submitCorrection(item)">
          <div class="form-row">
            <mat-form-field><mat-label>Produkttyp</mat-label><input matInput formControlName="productType" /></mat-form-field>
            <mat-form-field><mat-label>Hersteller</mat-label><input matInput formControlName="manufacturer" /></mat-form-field>
          </div>
          <div class="form-row">
            <mat-form-field><mat-label>Exaktes Modell</mat-label><input matInput formControlName="model" /></mat-form-field>
            <mat-form-field><mat-label>Variante</mat-label><input matInput formControlName="variant" /></mat-form-field>
          </div>
          <div class="form-row">
            <mat-form-field><mat-label>Attribut</mat-label><input matInput formControlName="attributeKey" /></mat-form-field>
            <mat-form-field><mat-label>Wert</mat-label><input matInput formControlName="attributeValue" /></mat-form-field>
          </div>
          <mat-form-field><mat-label>Begründung / Evidenz</mat-label><textarea matInput formControlName="evidence"></textarea></mat-form-field>
          <button mat-flat-button type="submit" [disabled]="correctionForm.invalid || savingCorrection()">Korrektur speichern</button>
        </form>
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
      <section class="section-head"><div><p class="eyebrow">Bewertung</p><h2>Marktwert- und Analysehistorie</h2></div></section>
      <div class="listing-grid">
        @for (observation of item.comparisonObservations; track observation.id) {
          <mat-card class="listing-card">
            <div class="row"><mat-chip>{{ observation.observationKind }}</mat-chip><span>{{ observation.platform }}</span></div>
            <h3>{{ observation.observedPrice }} {{ observation.currency }}</h3>
            <p>+ {{ observation.shippingCost }} Versand · {{ observation.condition ?? 'Zustand unbekannt' }}</p>
            <small>{{ observation.region ?? 'Region unbekannt' }} · {{ observation.observedAt }}</small>
          </mat-card>
        } @empty { <div class="empty">Keine passenden Vergleichsangebote vorhanden.</div> }
      </div>
      <div class="listing-grid">
        @for (evaluation of item.evaluations; track evaluation.id) {
          <mat-card class="listing-card">
            <div class="row"><mat-chip>{{ evaluation.calculationVersion }}</mat-chip><span>Datenqualität {{ evaluation.dataQualityScore }}</span></div>
            <h3>{{ evaluation.marketValueMedian ?? 'Keine belastbare Schätzung' }} {{ item.currency }}</h3>
            <p>Spanne {{ evaluation.marketValueMinimum ?? '–' }} bis {{ evaluation.marketValueMaximum ?? '–' }} · Marge {{ evaluation.estimatedMargin ?? '–' }}</p>
            <small>Deal {{ evaluation.dealScore ?? '–' }} · Risiko {{ evaluation.riskScore }}</small>
            <details><summary>Vergleichsgrundlage und Ausschlussgründe</summary>
              <pre>{{ evaluation.explanation['market'] | json }}</pre>
            </details>
          </mat-card>
        } @empty { <div class="empty">Noch keine Bewertungshistorie.</div> }
      </div>
      <div class="listing-grid">
        @for (analysis of item.analysisResults; track analysis.id) {
          <mat-card class="listing-card">
            <div class="row"><mat-chip>{{ analysis.analysisType }}</mat-chip><span>{{ analysis.modelName }} {{ analysis.modelVersion }}</span></div>
            <p>Prompt {{ analysis.promptVersion }} · Schema {{ analysis.resultSchemaVersion }}</p>
            @if (analysis.result['contradictions']) { <p><b>Widersprüche:</b> {{ analysis.result['contradictions'] | json }}</p> }
            @if (analysis.result['missingInformation']) { <p><b>Fehlende Angaben:</b> {{ analysis.result['missingInformation'] | json }}</p> }
            <details><summary>Strukturiertes Ergebnis</summary><pre>{{ analysis.result | json }}</pre></details>
          </mat-card>
        } @empty { <div class="empty">Noch keine Modell- oder Nutzeranalyse.</div> }
      </div>
      <section class="section-head"><div><p class="eyebrow">Revision</p><h2>Rohdaten und Feedback</h2></div></section>
      @for (snapshot of item.snapshots; track snapshot.id) {
        <mat-card class="form-card">
          <details><summary>{{ snapshot.providerVersion }} · {{ snapshot.fetchedAt }}</summary><pre>{{ snapshot.rawData | json }}</pre></details>
        </mat-card>
      }
      @for (entry of item.feedback; track entry.id) {
        <mat-card class="form-card"><b>{{ entry.feedbackType }}</b><span> · Basisversion {{ entry.baseListingVersion }}</span><p>{{ entry.note ?? '' }}</p></mat-card>
      }
    }
  `,
  styles: `.description { white-space: pre-wrap; line-height: 1.65; } .listing-image { width: 100%; aspect-ratio: 16 / 10; object-fit: contain; border-radius: 10px; background: #07120f; margin-bottom: 14px; } pre { overflow: auto; max-height: 24rem; white-space: pre-wrap; }`,
})
export class ListingDetailPage implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly id = inject(ActivatedRoute).snapshot.paramMap.get('id') ?? '';
  readonly listing = signal<ListingDetail | null>(null);
  readonly images = signal<ListingImage[]>([]);
  readonly imageUrls = signal<Record<string, string>>({});
  readonly loading = signal(false);
  readonly error = signal('');
  readonly savingCorrection = signal(false);
  readonly correctionForm = new FormGroup({
    productType: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    manufacturer: new FormControl('', { nonNullable: true }),
    model: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    variant: new FormControl('', { nonNullable: true }),
    attributeKey: new FormControl('', { nonNullable: true }),
    attributeValue: new FormControl('', { nonNullable: true }),
    evidence: new FormControl('Manuell am Angebot geprüft', { nonNullable: true, validators: [Validators.required] }),
  });

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

  async submitCorrection(item: ListingDetail): Promise<void> {
    if (this.correctionForm.invalid) return;
    const value = this.correctionForm.getRawValue();
    this.savingCorrection.set(true);
    try {
      const payload: FeedbackCreate = {
        feedbackType: 'correctedComponents',
        baseListingVersion: item.version,
        correctedProducts: [
          {
            productType: value.productType,
            manufacturer: value.manufacturer || null,
            model: value.model,
            variant: value.variant || null,
            quantity: 1,
            evidence: value.evidence,
          },
        ],
        correctedAttributes:
          value.attributeKey && value.attributeValue
            ? [{ productIndex: 0, key: value.attributeKey, value: value.attributeValue, unit: null }]
            : null,
      };
      await this.api.createFeedback(item.id, payload);
      this.correctionForm.patchValue({ model: '', variant: '', attributeKey: '', attributeValue: '' });
      await this.reload();
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Korrektur konnte nicht gespeichert werden');
    } finally {
      this.savingCorrection.set(false);
    }
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
