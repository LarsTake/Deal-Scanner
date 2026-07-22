import { Component, OnInit, inject, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import type { Product } from '@deal-scanner/contracts';

import { ApiService } from './api.service';

@Component({
  standalone: true,
  imports: [MatCardModule, MatChipsModule],
  template: `
    <header class="page-header"><div><p class="eyebrow">Normalisierung</p><h1>Produktkatalog</h1><p>Kanonische Produkte und erkannte Aliase aus Regel- und KI-Analysen.</p></div></header>
    @if (error()) { <div class="notice error">{{ error() }}</div> }
    <div class="listing-grid wide">
      @for (product of products(); track product.id) {
        <mat-card class="listing-card">
          <div class="row"><mat-chip>{{ product.categoryProfile }}</mat-chip><span>{{ product.productType }}</span></div>
          <h3>{{ product.manufacturer }} {{ product.model }} {{ product.variant }}</h3>
          <p>{{ product.aliases?.length ? product.aliases.join(' · ') : 'Keine zusätzlichen Aliase' }}</p>
          <small>Aktualisiert {{ product.updatedAt.slice(0, 10) }}</small>
        </mat-card>
      } @empty { <div class="empty">Der Katalog wird beim ersten erkannten Produkt aufgebaut.</div> }
    </div>
  `,
})
export class CatalogPage implements OnInit {
  private readonly api = inject(ApiService);
  readonly products = signal<Product[]>([]);
  readonly error = signal('');

  async ngOnInit(): Promise<void> {
    try {
      this.products.set((await this.api.products()).items);
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Produktkatalog konnte nicht geladen werden');
    }
  }
}
