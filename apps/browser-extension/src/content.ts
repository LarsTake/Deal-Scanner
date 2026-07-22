import type { ImportMessage, VisibleListing } from './types';

function text(root: ParentNode, selectors: string[]): string {
  for (const selector of selectors) {
    const value = root.querySelector(selector)?.textContent?.trim();
    if (value) return value;
  }
  return '';
}

function price(value: string): string {
  const match = value.match(/(\d{1,3}(?:[. ]\d{3})*(?:,\d{2})?)/);
  return match ? match[1].replace(/[. ]/g, '').replace(',', '.') : '0.00';
}

function externalId(url: string): string {
  return url.match(/\/(\d+)-\d+-\d+(?:[/?#]|$)/)?.[1] ?? crypto.randomUUID();
}

function visible(element: Element): boolean {
  const box = element.getBoundingClientRect();
  const style = getComputedStyle(element);
  return box.width > 0 && box.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
}

function imageUrls(root: ParentNode): string[] {
  const urls = [...root.querySelectorAll<HTMLImageElement>('img[src]')]
    .filter((image) => visible(image))
    .map((image) => image.currentSrc || image.src)
    .filter((url) => {
      try {
        return ['img.kleinanzeigen.de', 'img.classistatic.de'].includes(new URL(url, location.href).hostname);
      } catch {
        return false;
      }
    });
  return [...new Set(urls)].slice(0, 10);
}

function collectDetail(): VisibleListing[] {
  const title = text(document, ['h1', '[data-testid="ad-title"]']);
  if (!title) return [];
  const sellerName = text(document, [
    '[data-testid="user-profile-name"]',
    '#viewad-contact .text-body-regular-strong',
    '[class*="user"] [class*="name"]',
  ]);
  const sellerAge = text(document, ['[data-testid="user-profile-since"]', '[class*="user"] [class*="since"]']);
  const sellerRating = text(document, ['[data-testid="user-profile-rating"]', '[class*="user"] [class*="rating"]']);
  const listingLocation = text(document, ['#viewad-locality', '[data-testid="location"]']);
  return [{
    platform: 'kleinanzeigen',
    externalId: externalId(location.href),
    url: location.href,
    title,
    description: text(document, ['#viewad-description-text', '[data-testid="description"]']),
    price: price(text(document, ['#viewad-price', '[data-testid="price"]'])),
    currency: 'EUR',
    location: listingLocation,
    ...(sellerName ? {
      seller: {
        externalId: `${sellerName}:${listingLocation}`.toLocaleLowerCase('de-DE').replace(/[^a-z0-9]+/g, '-'),
        displayName: sellerName,
        accountAgeText: sellerAge || undefined,
        ratingText: sellerRating || undefined,
        location: listingLocation || undefined,
        rawData: { source: 'visibleBrowserPage' },
      },
    } : {}),
    categoryProfile: 'general',
    rawData: { source: 'visibleBrowserPage', capturedAt: new Date().toISOString(), imageUrls: imageUrls(document) },
    providerVersion: 'browser-extension-v1',
  }];
}

function collectCards(): VisibleListing[] {
  const listings: VisibleListing[] = [];
  const seen = new Set<string>();
  for (const card of document.querySelectorAll('article, li.ad-listitem')) {
    if (!visible(card)) continue;
    const anchor = card.querySelector<HTMLAnchorElement>('a[href*="/s-anzeige/"]');
    if (!anchor) continue;
    const url = new URL(anchor.href, location.href).href;
    const id = externalId(url);
    if (seen.has(id)) continue;
    seen.add(id);
    listings.push({
      platform: 'kleinanzeigen', externalId: id, url,
      title: text(card, ['h2', 'h3', '.ellipsis']), description: '',
      price: price(text(card, ['.aditem-main--middle--price-shipping--price', '[class*="price"]'])),
      currency: 'EUR', location: text(card, ['[class*="location"]']), categoryProfile: 'general',
      rawData: { source: 'visibleBrowserPage', capturedAt: new Date().toISOString(), imageUrls: imageUrls(card) },
      providerVersion: 'browser-extension-v1',
    });
  }
  return listings.filter((listing) => listing.title && listing.price !== '0.00');
}

async function importVisible(): Promise<void> {
  const button = document.querySelector<HTMLButtonElement>('#deal-scanner-import');
  const listings = location.pathname.includes('/s-anzeige/') ? collectDetail() : collectCards();
  if (!listings.length) { if (button) button.textContent = 'Keine sichtbaren Angebote'; return; }
  const message: ImportMessage = { type: 'IMPORT_VISIBLE_LISTINGS', listings };
  const result = await chrome.runtime.sendMessage(message) as { imported: number; error?: string };
  if (button) button.textContent = result.error ? `Fehler: ${result.error}` : `${result.imported} importiert`;
}

const button = document.createElement('button');
button.id = 'deal-scanner-import';
button.textContent = location.pathname.includes('/s-anzeige/') ? 'Angebot importieren' : 'Sichtbare Angebote importieren';
button.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:2147483647;padding:12px 16px;border:0;border-radius:10px;background:#57e6ae;color:#07120f;font:700 14px system-ui;box-shadow:0 8px 30px #0008;cursor:pointer';
button.addEventListener('click', () => void importVisible());
document.body.append(button);
