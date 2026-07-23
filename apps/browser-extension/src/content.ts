import type { ImportMessage, ImportOutcome, ImportResponseMessage, VisibleListing } from './types';

function text(root: ParentNode, selectors: string[]): string {
  for (const selector of selectors) {
    const value = root.querySelector(selector)?.textContent?.trim();
    if (value) return value;
  }
  return '';
}

export function price(value: string): string {
  const match = value.match(/(\d{1,3}(?:[. ]\d{3})*(?:,\d{2})?)/);
  return match ? match[1].replace(/[. ]/g, '').replace(',', '.') : '0.00';
}

export function euroPrice(value: string): string {
  const match = value.match(/(\d{1,3}(?:[. ]\d{3})*(?:,\d{2})?)\s*€/);
  return match ? match[1].replace(/[. ]/g, '').replace(',', '.') : '0.00';
}

export function externalId(url: string): string {
  return url.match(/\/(\d+)-\d+-\d+(?:[/?#]|$)/)?.[1] ?? crypto.randomUUID();
}

function visible(element: Element): boolean {
  const box = element.getBoundingClientRect();
  const style = getComputedStyle(element);
  return box.width > 0 && box.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
}

function listingUrl(element: Element): string | null {
  const value = element instanceof HTMLAnchorElement
    ? element.href
    : element.getAttribute('data-href') ?? element.getAttribute('href');
  if (!value) return null;
  try {
    const url = new URL(value, location.href);
    return url.hostname.endsWith('kleinanzeigen.de') && url.pathname.includes('/s-anzeige/')
      ? url.href
      : null;
  } catch {
    return null;
  }
}

function resultCard(candidate: Element): Element {
  let current: Element | null = candidate;
  let structuralFallback: Element | null = null;
  for (let depth = 0; current && depth < 8; depth += 1) {
    if (!structuralFallback && current.matches('article, li.ad-listitem, [data-adid], [data-testid*="ad"]')) {
      structuralFallback = current;
    }
    const hasListingTarget = listingUrl(current) !== null
      || current.querySelector('a[href*="/s-anzeige/"], [data-href*="/s-anzeige/"]') !== null;
    if (hasListingTarget && euroPrice(current.textContent ?? '') !== '0.00') return current;
    current = current.parentElement;
  }
  return structuralFallback ?? candidate;
}

function titleFromUrl(value: string): string {
  try {
    const slug = new URL(value).pathname.split('/s-anzeige/')[1]?.split('/')[0] ?? '';
    return decodeURIComponent(slug).replace(/[-_]+/g, ' ').trim();
  } catch {
    return '';
  }
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

export function collectDetail(): VisibleListing[] {
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

export function collectCards(): VisibleListing[] {
  const listings: VisibleListing[] = [];
  const seen = new Set<string>();
  const candidates = document.querySelectorAll<HTMLAnchorElement | HTMLElement>('a[href], [data-href]');
  for (const candidate of candidates) {
    const url = listingUrl(candidate);
    if (!url) continue;
    const card = resultCard(candidate);
    const id = externalId(url);
    if (seen.has(id)) continue;
    const title = text(card, ['h2', 'h3', '[data-testid*="title"]', '.ellipsis'])
      || candidate.getAttribute('aria-label')?.trim()
      || candidate.getAttribute('title')?.trim()
      || candidate.textContent?.trim()
      || titleFromUrl(url);
    const selectedPrice = text(card, [
      '.aditem-main--middle--price-shipping--price',
      '[data-testid*="price"]',
      '[class*="price"]',
    ]);
    const listingPrice = euroPrice(selectedPrice) !== '0.00'
      ? euroPrice(selectedPrice)
      : euroPrice(card.textContent ?? '');
    if (!title || listingPrice === '0.00') continue;
    seen.add(id);
    if (card instanceof HTMLElement) card.dataset.dealScannerExternalId = id;
    listings.push({
      platform: 'kleinanzeigen', externalId: id, url,
      title,
      description: text(card, [
        '.aditem-main--middle--description',
        '[data-testid*="description"]',
        '[class*="description"]',
      ]),
      price: listingPrice,
      currency: 'EUR',
      location: text(card, [
        '[data-testid="location"]',
        '.aditem-main--top--left',
        '[class*="location"]',
      ]),
      categoryProfile: 'general',
      rawData: { source: 'visibleBrowserPage', capturedAt: new Date().toISOString(), imageUrls: imageUrls(card) },
      providerVersion: 'browser-extension-v1',
    });
  }
  return listings;
}

function outcomeText(outcome: ImportOutcome): string {
  if (outcome.dealScore !== null) {
    const risk = outcome.riskScore === null ? '–' : String(outcome.riskScore);
    const quality = outcome.dataQualityScore === null ? '–' : String(outcome.dataQualityScore);
    return `Deal ${outcome.dealScore} · Risiko ${risk} · Daten ${quality}`;
  }
  return outcome.snapshotCreated ? 'Importiert · Analyse offen' : 'Bereits bekannt · Analyse offen';
}

export function renderImportOutcomes(outcomes: ImportOutcome[]): void {
  const cards = [...document.querySelectorAll<HTMLElement>('[data-deal-scanner-external-id]')];
  for (const outcome of outcomes) {
    const detailPage = location.pathname.includes('/s-anzeige/');
    const host = cards.find((card) => card.dataset.dealScannerExternalId === outcome.externalId)
      ?? (detailPage ? document.body : null);
    if (!host) continue;
    const badgeId = `deal-scanner-score-${outcome.externalId}`;
    let badge = document.getElementById(badgeId);
    if (!badge) {
      badge = document.createElement('div');
      badge.id = badgeId;
      badge.dataset.dealScannerBadge = outcome.externalId;
      host.append(badge);
    }
    badge.textContent = outcomeText(outcome);
    badge.style.cssText = detailPage
      ? 'position:fixed;right:20px;bottom:72px;z-index:2147483647;padding:9px 12px;border-radius:9px;background:#0f1c19;color:#57e6ae;font:700 13px system-ui;box-shadow:0 8px 30px #0008'
      : 'display:inline-block;margin:8px;padding:7px 10px;border-radius:8px;background:#0f1c19;color:#57e6ae;font:700 12px system-ui';
  }
}

async function importVisible(): Promise<void> {
  const button = document.querySelector<HTMLButtonElement>('#deal-scanner-import');
  const listings = location.pathname.includes('/s-anzeige/') ? collectDetail() : collectCards();
  if (!listings.length) { if (button) button.textContent = 'Keine sichtbaren Angebote'; return; }
  const message: ImportMessage = { type: 'IMPORT_VISIBLE_LISTINGS', listings };
  const result = await chrome.runtime.sendMessage(message) as ImportResponseMessage;
  renderImportOutcomes(result.results ?? []);
  if (button) {
    const known = result.results.filter((item) => !item.snapshotCreated).length;
    button.textContent = result.error
      ? `Fehler: ${result.error}`
      : `${result.imported} verarbeitet${known ? ` · ${known} bekannt` : ''}`
        + `${result.imageFailures ? ` · ${result.imageFailures} ohne Bild` : ''}`;
  }
}

const button = document.createElement('button');
button.id = 'deal-scanner-import';
button.textContent = location.pathname.includes('/s-anzeige/')
  ? 'Angebot importieren'
  : 'Alle Angebote dieser Seite importieren';
button.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:2147483647;padding:12px 16px;border:0;border-radius:10px;background:#57e6ae;color:#07120f;font:700 14px system-ui;box-shadow:0 8px 30px #0008;cursor:pointer';
button.addEventListener('click', () => void importVisible());
document.body.append(button);
