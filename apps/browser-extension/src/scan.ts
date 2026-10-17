export interface ScanOptions { maxPages: number; maxListings: number; delaySeconds: number; }
export interface ScanState extends ScanOptions {
  id: string;
  status: 'running' | 'done' | 'stopped' | 'error';
  phase: 'search' | 'detail';
  currentUrl: string;
  nextPage: string | null;
  pending: string[];
  visitedPages: string[];
  visitedListings: string[];
  imported: number;
  message: string;
}

export function marketplaceUrl(value: string): string {
  const url = new URL(value);
  if (url.protocol !== 'https:' || !['www.kleinanzeigen.de', 'kleinanzeigen.de'].includes(url.hostname)
      || url.username || url.password || url.port) throw new Error('Bitte eine Kleinanzeigen-Seite öffnen.');
  url.hash = '';
  if (url.pathname.includes('/s-anzeige/')) url.search = '';
  return url.href;
}

export function createScan(url: string, options: ScanOptions): ScanState {
  if (!Number.isInteger(options.maxPages) || options.maxPages < 1 || options.maxPages > 20
      || !Number.isInteger(options.maxListings) || options.maxListings < 1 || options.maxListings > 200
      || !Number.isInteger(options.delaySeconds) || options.delaySeconds < 3 || options.delaySeconds > 60) {
    throw new Error('Erlaubt: 1–20 Seiten, 1–200 Angebote und 3–60 Sekunden Pause.');
  }
  const currentUrl = marketplaceUrl(url);
  const detail = new URL(currentUrl).pathname.includes('/s-anzeige/');
  return { ...options, id: crypto.randomUUID(), status: 'running', phase: detail ? 'detail' : 'search',
    currentUrl, nextPage: null, pending: detail ? [currentUrl] : [], visitedPages: [], visitedListings: [],
    imported: 0, message: 'Durchlauf gestartet.' };
}

function nextPageOrDone(state: ScanState): ScanState {
  if (state.nextPage && state.visitedPages.length < state.maxPages && !state.visitedPages.includes(state.nextPage)
      && state.visitedListings.length < state.maxListings) {
    return { ...state, phase: 'search', currentUrl: state.nextPage, nextPage: null, pending: [] };
  }
  return { ...state, status: 'done', message: `Fertig: ${state.imported} Angebote importiert.` };
}

export function searchStep(state: ScanState, links: string[], next: string | null): ScanState {
  const seenIds = new Set(state.visitedListings.map((url) => new URL(url).pathname.split('/').pop()));
  const unique = new Map<string, string>();
  for (const link of links) {
    const url = marketplaceUrl(link);
    const path = new URL(url).pathname;
    if (!path.includes('/s-anzeige/')) continue;
    const key = path.split('/').pop()!;
    if (!seenIds.has(key)) unique.set(key, url);
  }
  const pending = [...unique.values()].slice(0, state.maxListings - state.visitedListings.length);
  const nextPage = next ? marketplaceUrl(next) : null;
  if (nextPage && new URL(nextPage).pathname.includes('/s-anzeige/')) throw new Error('Ungültiger Link zur nächsten Ergebnisseite.');
  const updated: ScanState = { ...state, pending, nextPage,
    visitedPages: [...state.visitedPages, state.currentUrl] };
  return pending.length ? { ...updated, phase: 'detail', currentUrl: pending[0] } : nextPageOrDone(updated);
}

export function detailStep(state: ScanState, imported: number): ScanState {
  const updated = { ...state, imported: state.imported + imported, pending: state.pending.slice(1),
    visitedListings: [...state.visitedListings, state.currentUrl] };
  if (updated.visitedListings.length >= state.maxListings) return { ...updated, status: 'done', message: `Angebotslimit erreicht: ${updated.imported} importiert.` };
  return updated.pending.length ? { ...updated, currentUrl: updated.pending[0] } : nextPageOrDone(updated);
}
