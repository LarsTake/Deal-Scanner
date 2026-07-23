// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest';

import { collectCards, collectDetail, euroPrice, externalId, price, renderImportOutcomes } from './content';

describe('visible Kleinanzeigen extraction', () => {
  beforeEach(() => {
    history.replaceState({}, '', '/s-anzeige/gaming-pc/1234567890-228-1234');
    document.body.innerHTML = `
      <h1>Gaming-PC mit RTX 4070S</h1>
      <div id="viewad-price">1.299,00 €</div>
      <div id="viewad-description-text">Abholung und Funktionstest möglich</div>
      <div id="viewad-locality">Hamburg</div>
      <div data-testid="user-profile-name">Privater Anbieter</div>
      <div data-testid="user-profile-since">Aktiv seit 2018</div>
    `;
  });

  it('normalizes German prices and stable listing ids', () => {
    expect(price('VB 1.299,00 €')).toBe('1299.00');
    expect(euroPrice('RTX 5070 · 71636 Ludwigsburg · 1.150 € VB')).toBe('1150');
    expect(externalId(location.href)).toBe('1234567890');
  });

  it('extracts only visible page data including seller evidence', () => {
    const [listing] = collectDetail();
    expect(listing.title).toBe('Gaming-PC mit RTX 4070S');
    expect(listing.price).toBe('1299.00');
    expect(listing.location).toBe('Hamburg');
    expect(listing.seller?.displayName).toBe('Privater Anbieter');
    expect(listing.seller?.rawData.source).toBe('visibleBrowserPage');
  });

  it('renders a known listing score directly on the open detail page', () => {
    renderImportOutcomes([{
      externalId: '1234567890',
      listingId: '00000000-0000-4000-8000-000000000001',
      snapshotCreated: false,
      dealScore: 82,
      riskScore: 19,
      dataQualityScore: 74,
    }]);

    expect(document.querySelector('[data-deal-scanner-badge="1234567890"]')?.textContent)
      .toBe('Deal 82 · Risiko 19 · Daten 74');
  });

  it('marks unchanged imports as already known while analysis is pending', () => {
    renderImportOutcomes([{
      externalId: '1234567890',
      listingId: '00000000-0000-4000-8000-000000000001',
      snapshotCreated: false,
      dealScore: null,
      riskScore: null,
      dataQualityScore: null,
    }]);

    expect(document.querySelector('[data-deal-scanner-badge="1234567890"]')?.textContent)
      .toBe('Bereits bekannt · Analyse offen');
  });

  it('collects every loaded result card without opening individual listings', () => {
    history.replaceState({}, '', '/s-pc/k0');
    document.body.innerHTML = `
      <ol>
        <li class="ad-listitem">
          <article class="aditem" data-adid="3462624376">
            <a href="/s-anzeige/gaming-pc/3462624376-228-1944"></a>
            <h2 class="ellipsis">Gaming PC RTX 5070 Ti</h2>
            <p class="aditem-main--middle--description">Ryzen 7, 32 GB RAM und 2 TB SSD</p>
            <div class="aditem-main--middle--price-shipping--price">1.499 € VB</div>
            <div class="aditem-main--top--left">Hamburg</div>
          </article>
        </li>
        <article data-adid="3462624377"
          data-href="/s-anzeige/gaming-pc/3462624377-228-1944">
          <h2>Gaming PC RTX 4080</h2>
          <div data-testid="price">1.899 €</div>
          <div data-testid="location">Berlin</div>
        </article>
      </ol>
    `;

    expect(collectCards()).toEqual([
      expect.objectContaining({
        externalId: '3462624376',
        title: 'Gaming PC RTX 5070 Ti',
        description: 'Ryzen 7, 32 GB RAM und 2 TB SSD',
        price: '1499',
        location: 'Hamburg',
      }),
      expect.objectContaining({
        externalId: '3462624377',
        title: 'Gaming PC RTX 4080',
        price: '1899',
        location: 'Berlin',
      }),
    ]);
  });

  it('finds class-independent dynamic cards through their link, euro price and URL slug', () => {
    history.replaceState({}, '', '/m-suche-verwenden.html?id=fixture');
    document.body.innerHTML = `
      <main>
        <section>
          <div>
            <a href="/s-anzeige/gaming-pc-rtx-4070/3462624388-228-1944">
              <img alt="Gaming-PC" />
            </a>
            <span>71636 Ludwigsburg</span>
            <span>850 € VB</span>
          </div>
        </section>
      </main>
    `;

    expect(collectCards()).toEqual([
      expect.objectContaining({
        externalId: '3462624388',
        title: 'gaming pc rtx 4070',
        price: '850',
      }),
    ]);
  });
});
