import { Component, OnInit, inject, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatButtonModule } from '@angular/material/button';
import type { PriceObservation, Product } from '@deal-scanner/contracts';

import { ApiService } from './api.service';
import { FileAccessService } from './file-access.service';

@Component({
  standalone: true,
  imports: [MatButtonModule, MatCardModule, MatChipsModule],
  template: `
    <header class="page-header"><div><p class="eyebrow">Marktdaten</p><h1>Preisverläufe</h1><p>Bestätigte Verkäufe, manuelle Verkäufe und aktive Angebote bleiben getrennt gewichtet.</p></div><button mat-flat-button (click)="importCsv()">CSV importieren</button></header>
    @if (error()) { <div class="notice error">{{ error() }}</div> }
    @if (importStatus()) { <div class="notice">{{ importStatus() }}</div> }
    <div class="listing-grid wide">
      @for (observation of observations(); track observation.id) {
        <mat-card class="listing-card">
          <div class="row"><mat-chip>{{ observation.observationKind }}</mat-chip><span>{{ observation.observedAt.slice(0, 10) }}</span></div>
          <h3>{{ productName(observation.canonicalProductId) }}</h3>
          <div class="price">{{ observation.observedPrice }} {{ observation.currency }} <small>+ {{ observation.shippingCost }} Versand</small></div>
          <p>{{ observation.platform }} · Quellenqualität {{ observation.sourceQuality }}</p>
        </mat-card>
      } @empty { <div class="empty">Noch keine Preisbeobachtungen vorhanden.</div> }
    </div>
  `,
})
export class PricesPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly files = inject(FileAccessService);
  readonly products = signal<Product[]>([]);
  readonly observations = signal<PriceObservation[]>([]);
  readonly error = signal('');
  readonly importStatus = signal('');

  async ngOnInit(): Promise<void> {
    try {
      const [products, observations] = await Promise.all([
        this.api.products(),
        this.api.priceObservations(),
      ]);
      this.products.set(products.items);
      this.observations.set(observations);
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Marktdaten konnten nicht geladen werden');
    }
  }

  productName(productId?: string | null): string {
    const product = this.products().find((item) => item.id === productId);
    return product ? [product.manufacturer, product.model, product.variant].filter(Boolean).join(' ') : 'Nicht zugeordnet';
  }

  async importCsv(): Promise<void> {
    this.error.set('');
    this.importStatus.set('');
    try {
      const file = await this.files.selectCsv();
      if (!file) return;
      const result = await this.api.importMarketDataCsv(file.name, file.content);
      this.importStatus.set(`${result.rowsImported} Zeilen aus ${result.filename} importiert.`);
      this.observations.set(await this.api.priceObservations());
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'CSV-Import fehlgeschlagen');
    }
  }
}
