import type {
  CrawlCandidate,
  CrawlListingsMessage,
  CrawlProgressMessage,
  ExtensionMessage,
  ImportMessage,
  ImportOutcome,
  ImportResponseMessage,
  VisibleListing,
} from './types';

function text(root: ParentNode, selectors: string[]): string {
  for (const selector of selectors) {
    const value = root.querySelector(selector)?.textContent?.trim();
    if (value) return value;
  }
  return '';
}

export function price(value: string): string {
  const match = value.match(/\d[\d., ]*/);
  if (!match) return '0.00';
  let normalized = match[0].trim().replace(/ /g, '');
  const comma = normalized.lastIndexOf(',');
  const dot = normalized.lastIndexOf('.');
  if (comma >= 0 && dot >= 0) {
    const decimalSeparator = comma > dot ? ',' : '.';
    const thousandsSeparator = decimalSeparator === ',' ? '.' : ',';
    normalized = normalized.replaceAll(thousandsSeparator, '').replace(decimalSeparator, '.');
  } else if (comma >= 0) {
    normalized = normalized.length - comma - 1 === 2
      ? normalized.replace(',', '.')
      : normalized.replaceAll(',', '');
  } else if (dot >= 0 && normalized.length - dot - 1 !== 2) {
    normalized = normalized.replaceAll('.', '');
  }
  return normalized;
}

export function euroPrice(value: string): string {
  const match = value.match(/(\d{1,3}(?:[. ]\d{3})*(?:,\d{2})?)\s*€/);
  return match ? price(match[1]) : '0.00';
}

export function externalId(url: string): string {
  const kleinanzeigenId = url.match(/\/(\d+)-\d+-\d+(?:[/?#]|$)/)?.[1];
  if (kleinanzeigenId) return kleinanzeigenId;
  let hash = 2166136261;
  for (const character of url) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return `page-${(hash >>> 0).toString(16).padStart(8, '0')}`;
}

function platformName(): string {
  if (location.hostname.endsWith('kleinanzeigen.de')) return 'kleinanzeigen';
  return location.hostname
    .toLocaleLowerCase('en-US')
    .replace(/^www\./, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 32) || 'web';
}

function meta(selectors: string[]): string {
  for (const selector of selectors) {
    const value = document.querySelector<HTMLMetaElement>(selector)?.content?.trim();
    if (value) return value;
  }
  return '';
}

function currency(value: string): string {
  if (value.includes('$')) return 'USD';
  if (value.includes('£')) return 'GBP';
  return meta(['meta[property="product:price:currency"]', 'meta[itemprop="priceCurrency"]']).toUpperCase() || 'EUR';
}

function structuredProducts(): Record<string, unknown>[] {
  const products: Record<string, unknown>[] = [];
  for (const script of document.querySelectorAll<HTMLScriptElement>('script[type="application/ld+json"]')) {
    try {
      const value = JSON.parse(script.textContent ?? 'null') as unknown;
      const queue = Array.isArray(value) ? [...value] : [value];
      while (queue.length) {
        const item = queue.shift();
        if (!item || typeof item !== 'object') continue;
        const record = item as Record<string, unknown>;
        if (Array.isArray(record['@graph'])) queue.push(...record['@graph']);
        const type = String(record['@type'] ?? '').toLocaleLowerCase('en-US');
        if (['product', 'vehicle', 'realestatelisting', 'offer'].some((candidate) => type.includes(candidate))) {
          products.push(record);
        }
      }
    } catch {
      // Invalid third-party JSON-LD is ignored; visible DOM extraction remains available.
    }
  }
  return products;
}

function structuredOffer(product: Record<string, unknown> | undefined): Record<string, unknown> | undefined {
  const offer = product?.['offers'];
  if (Array.isArray(offer)) return offer.find((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'));
  return offer && typeof offer === 'object' ? offer as Record<string, unknown> : undefined;
}

function categoryProfile(title: string, description = ''): string {
  const value = `${title} ${description}`.toLocaleLowerCase('de-DE');
  if (/\b(wohnung|haus|immobilie|grundst(?:ü|u)ck|miete|kaufpreis|wohnfl(?:ä|a)che)\b/.test(value)) return 'real_estate';
  if (/\b(auto|fahrzeug|motorrad|kilometerstand|erstzulassung)\b/.test(value)) return 'vehicles';
  if (/\b(gaming.?pc|grafikkarte|gpu|prozessor|cpu|mainboard|arbeitsspeicher|ram)\b/.test(value)) return 'computer';
  if (/\b(fpv|drohne|quadcopter|flight controller)\b/.test(value)) return 'fpv';
  if (/\b(simracing|lenkrad|wheelbase|pedale)\b/.test(value)) return 'simracing';
  if (/\b(elektronik|kamera|fernseher|smartphone|tablet|laptop)\b/.test(value)) return 'electronics';
  return 'general';
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
        return new URL(url, location.href).protocol === 'https:';
      } catch {
        return false;
      }
    });
  const socialImage = meta(['meta[property="og:image"]', 'meta[name="twitter:image"]']);
  if (socialImage) urls.unshift(new URL(socialImage, location.href).href);
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
  const description = text(document, ['#viewad-description-text', '[data-testid="description"]']);
  return [{
    platform: 'kleinanzeigen',
    externalId: externalId(location.href),
    url: location.href,
    title,
    description,
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
    categoryProfile: categoryProfile(title, description),
    rawData: { source: 'visibleBrowserPage', capturedAt: new Date().toISOString(), imageUrls: imageUrls(document) },
    providerVersion: 'browser-extension-v1',
  }];
}

export function collectUniversalDetail(): VisibleListing[] {
  if (location.hostname.endsWith('kleinanzeigen.de')) return collectDetail();
  const product = structuredProducts()[0];
  const offer = structuredOffer(product);
  const title = String(product?.['name'] ?? '')
    || meta(['meta[property="og:title"]', 'meta[name="twitter:title"]'])
    || text(document, ['h1', '[itemprop="name"]'])
    || document.title;
  const description = String(product?.['description'] ?? '')
    || meta(['meta[property="og:description"]', 'meta[name="description"]'])
    || text(document, ['[itemprop="description"]', '[class*="description"]']);
  const priceText = String(
    offer?.['price']
    ?? product?.['price']
    ?? meta(['meta[property="product:price:amount"]', 'meta[itemprop="price"]'])
    ?? text(document, ['[itemprop="price"]', '[data-testid*="price"]', '[class*="price"]']),
  );
  const normalizedPrice = price(priceText);
  if (!title.trim() || normalizedPrice === '0.00') return [];
  const structuredImages = product?.['image'];
  const images = [
    ...(Array.isArray(structuredImages) ? structuredImages : [structuredImages]),
    ...imageUrls(document),
  ].filter((value): value is string => typeof value === 'string' && value.startsWith('https://'));
  const identifier = String(
    product?.['productID']
    ?? product?.['sku']
    ?? meta(['meta[property="product:retailer_item_id"]'])
    ?? externalId(location.href),
  );
  const detectedCurrency = String(offer?.['priceCurrency'] ?? currency(priceText)).toUpperCase();
  return [{
    platform: platformName(),
    externalId: identifier.slice(0, 255),
    url: location.href,
    title: title.trim().slice(0, 500),
    description: description.trim().slice(0, 100_000),
    price: normalizedPrice,
    currency: /^[A-Z]{3}$/.test(detectedCurrency) ? detectedCurrency : 'EUR',
    location: text(document, ['[itemprop="address"]', '[data-testid*="location"]', '[class*="location"]']) || undefined,
    categoryProfile: categoryProfile(title, description),
    rawData: {
      source: 'visibleBrowserPage',
      capturedAt: new Date().toISOString(),
      imageUrls: [...new Set(images)].slice(0, 10),
      pageHost: location.hostname,
      extractionMethod: product ? 'json-ld+visible-dom' : 'visible-dom',
    },
    providerVersion: 'browser-extension-universal-v2',
  }];
}

export function collectUniversalCandidates(): CrawlCandidate[] {
  const kleinanzeigen = collectCards();
  if (kleinanzeigen.length) return kleinanzeigen.map((listing) => ({ url: listing.url, title: listing.title }));
  const candidates: CrawlCandidate[] = [];
  const seen = new Set<string>();
  for (const anchor of document.querySelectorAll<HTMLAnchorElement>('a[href]')) {
    let url: URL;
    try {
      url = new URL(anchor.href, location.href);
    } catch {
      continue;
    }
    if (!['http:', 'https:'].includes(url.protocol) || url.hostname !== location.hostname || url.href === location.href) continue;
    const card = anchor.closest('article, li, [data-testid*="item"], [data-testid*="card"], [class*="listing"], [class*="product"], [class*="card"]');
    if (!card || !visible(card)) continue;
    const cardPrice = text(card, ['[itemprop="price"]', '[data-testid*="price"]', '[class*="price"]'])
      || card.textContent
      || '';
    if (price(cardPrice) === '0.00') continue;
    const title = text(card, ['h2', 'h3', '[itemprop="name"]', '[data-testid*="title"]'])
      || anchor.getAttribute('aria-label')
      || anchor.getAttribute('title')
      || anchor.textContent
      || '';
    if (!title.trim() || seen.has(url.href)) continue;
    seen.add(url.href);
    candidates.push({ url: url.href, title: title.trim().slice(0, 180) });
    if (candidates.length >= 50) break;
  }
  return candidates;
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
    const description = text(card, [
      '.aditem-main--middle--description',
      '[data-testid*="description"]',
      '[class*="description"]',
    ]);
    listings.push({
      platform: 'kleinanzeigen', externalId: id, url,
      title,
      description,
      price: listingPrice,
      currency: 'EUR',
      location: text(card, [
        '[data-testid="location"]',
        '.aditem-main--top--left',
        '[class*="location"]',
      ]),
      categoryProfile: categoryProfile(title, description),
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
  const button = document.querySelector<HTMLButtonElement>('#deal-scanner-import-current');
  const listings = location.hostname.endsWith('kleinanzeigen.de') && location.pathname.includes('/s-anzeige/')
    ? collectDetail()
    : collectUniversalDetail();
  if (!listings.length) { if (button) button.textContent = 'Keine sichtbaren Angebote'; return; }
  if (button) {
    button.disabled = true;
    button.textContent = `${listings.length} Angebot${listings.length === 1 ? '' : 'e'} werden importiert …`;
  }
  const message: ImportMessage = { type: 'IMPORT_VISIBLE_LISTINGS', listings };
  try {
    const result = await chrome.runtime.sendMessage(message) as ImportResponseMessage | undefined;
    if (!result) throw new Error('Der Hintergrunddienst hat keine Antwort geliefert.');
    renderImportOutcomes(result.results ?? []);
    if (button) {
      const known = result.results.filter((item) => !item.snapshotCreated).length;
      button.textContent = result.error
        ? `Fehler: ${result.error}`
        : `${result.imported} verarbeitet${known ? ` · ${known} bekannt` : ''}`
          + `${result.imageFailures ? ` · ${result.imageFailures} ohne Bild` : ''}`;
    }
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'Unbekannter Erweiterungsfehler';
    if (button) {
      button.textContent = `Fehler: ${detail}. Erweiterung neu laden und erneut versuchen.`;
    }
  } finally {
    if (button) button.disabled = false;
  }
}

function renderProgress(progress: CrawlProgressMessage): void {
  const status = document.querySelector<HTMLElement>('#deal-scanner-progress');
  const log = document.querySelector<HTMLElement>('#deal-scanner-log');
  if (!status || !log) return;
  const cancel = document.querySelector<HTMLButtonElement>('#deal-scanner-cancel');
  if (cancel) cancel.disabled = progress.status === 'complete';
  status.textContent = progress.status === 'complete'
    ? `Fertig: ${progress.detail ?? `${progress.total} Angebote geprüft`}`
    : `${progress.current}/${progress.total} · ${progress.status.toUpperCase()} · ${progress.title}`;
  if (progress.status !== 'complete') {
    const entry = document.createElement('div');
    entry.textContent = `${progress.current}. ${progress.title} — ${progress.status}${progress.detail ? `: ${progress.detail}` : ''}`;
    entry.style.cssText = `padding:5px 0;border-top:1px solid #29413a;color:${progress.status === 'error' ? '#ff9d91' : '#b8cbc5'}`;
    log.prepend(entry);
    while (log.children.length > 8) log.lastElementChild?.remove();
  }
}

async function crawlListings(): Promise<void> {
  const candidates = collectUniversalCandidates();
  const button = document.querySelector<HTMLButtonElement>('#deal-scanner-crawl');
  if (!candidates.length) {
    if (button) button.textContent = 'Keine Angebotsliste erkannt';
    return;
  }
  if (button) {
    button.disabled = true;
    button.textContent = `${candidates.length} Angebote werden geprüft …`;
  }
  const cancel = document.querySelector<HTMLButtonElement>('#deal-scanner-cancel');
  if (cancel) cancel.disabled = false;
  const message: CrawlListingsMessage = { type: 'CRAWL_LISTINGS', candidates };
  try {
    const result = await chrome.runtime.sendMessage(message) as ImportResponseMessage | undefined;
    if (!result) throw new Error('Der Hintergrunddienst hat keine Antwort geliefert.');
    if (button) {
      button.textContent = result.error
        ? `Abgebrochen: ${result.error}`
        : `${result.imported} Angebote gespeichert`;
    }
  } catch (error) {
    if (button) button.textContent = `Fehler: ${error instanceof Error ? error.message : 'Unbekannt'}`;
  } finally {
    if (button) button.disabled = false;
    if (cancel) cancel.disabled = true;
  }
}

function mountPanel(): void {
  if (document.querySelector('#deal-scanner-panel')) return;
  const candidates = collectUniversalCandidates();
  const panel = document.createElement('aside');
  panel.id = 'deal-scanner-panel';
  panel.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:2147483647;width:360px;max-width:calc(100vw - 40px);padding:14px;border:1px solid #315148;border-radius:13px;background:#0b1714f2;color:#eef8f5;font:13px system-ui;box-shadow:0 12px 38px #000a;backdrop-filter:blur(12px)';
  panel.innerHTML = `
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:center">
      <strong style="color:#57e6ae">Deal Scanner · ${location.hostname}</strong>
      <button id="deal-scanner-close" title="Schließen" style="border:0;background:transparent;color:#b8cbc5;font-size:18px;cursor:pointer">×</button>
    </div>
    <div id="deal-scanner-progress" style="margin:9px 0;color:#b8cbc5">
      ${candidates.length ? `${candidates.length} Angebotslinks erkannt` : 'Aktuelle Angebotsseite bereit'}
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button id="deal-scanner-import-current" style="padding:9px 11px;border:0;border-radius:8px;background:#57e6ae;color:#07120f;font-weight:800;cursor:pointer">Aktuelles Angebot speichern</button>
      <button id="deal-scanner-crawl" ${candidates.length ? '' : 'disabled'} style="padding:9px 11px;border:1px solid #57e6ae;border-radius:8px;background:transparent;color:#57e6ae;font-weight:800;cursor:pointer">Liste einzeln prüfen (${candidates.length})</button>
      <button id="deal-scanner-cancel" disabled style="padding:9px 11px;border:1px solid #ff9d91;border-radius:8px;background:transparent;color:#ff9d91;font-weight:800;cursor:pointer">Stoppen</button>
    </div>
    <div id="deal-scanner-log" style="margin-top:9px;max-height:180px;overflow:auto"></div>
  `;
  panel.querySelector('#deal-scanner-close')?.addEventListener('click', () => panel.remove());
  panel.querySelector('#deal-scanner-import-current')?.addEventListener('click', () => void importVisible());
  panel.querySelector('#deal-scanner-crawl')?.addEventListener('click', () => void crawlListings());
  panel.querySelector('#deal-scanner-cancel')?.addEventListener('click', () => {
    void chrome.runtime.sendMessage({ type: 'CANCEL_CRAWL' });
  });
  document.body.append(panel);
}

if (typeof chrome !== 'undefined') {
  chrome.runtime.onMessage.addListener((message: ExtensionMessage, _sender, sendResponse) => {
    if (message.type === 'EXTRACT_CURRENT_LISTING') {
      sendResponse(collectUniversalDetail()[0] ?? null);
      return false;
    }
    if (message.type === 'CRAWL_PROGRESS') {
      renderProgress(message);
      return false;
    }
    if (message.type === 'SHOW_PANEL') {
      mountPanel();
      sendResponse(true);
      return false;
    }
    return false;
  });
}

mountPanel();
