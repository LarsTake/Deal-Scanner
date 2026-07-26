// @vitest-environment jsdom
// @vitest-environment-options {"url":"https://shop.example/products/camera-42"}

import { beforeEach, describe, expect, it } from 'vitest';

import { collectUniversalCandidates, collectUniversalDetail, externalId } from './content';

describe('universal offer extraction', () => {
  beforeEach(() => {
    document.head.innerHTML = '';
    document.body.innerHTML = '';
  });

  it('extracts a product from JSON-LD and visible page data', () => {
    document.head.innerHTML = `
      <script type="application/ld+json">
        {
          "@type": "Product",
          "name": "Sony Alpha Kamera",
          "description": "Gebraucht, technisch einwandfrei",
          "sku": "camera-42",
          "image": "https://cdn.example/camera.jpg",
          "offers": { "@type": "Offer", "price": "799.00", "priceCurrency": "EUR" }
        }
      </script>
    `;

    expect(collectUniversalDetail()).toEqual([
      expect.objectContaining({
        platform: 'shop-example',
        externalId: 'camera-42',
        title: 'Sony Alpha Kamera',
        price: '799.00',
        currency: 'EUR',
        providerVersion: 'browser-extension-universal-v2',
      }),
    ]);
  });

  it('detects same-site offer cards for the sequential crawler', () => {
    document.body.innerHTML = `
      <article>
        <a href="/products/camera-43"><h2>Sony Alpha II</h2></a>
        <span class="price">899 €</span>
      </article>
    `;
    document.querySelector('article')!.getBoundingClientRect = () => ({
      width: 320,
      height: 180,
      top: 0,
      right: 320,
      bottom: 180,
      left: 0,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    expect(collectUniversalCandidates()).toEqual([
      { url: 'https://shop.example/products/camera-43', title: 'Sony Alpha II' },
    ]);
  });

  it('creates stable ids for sites without marketplace item ids', () => {
    expect(externalId('https://shop.example/products/camera-42'))
      .toBe(externalId('https://shop.example/products/camera-42'));
  });
});
