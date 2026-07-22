// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest';

import { collectDetail, externalId, price } from './content';

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
});
