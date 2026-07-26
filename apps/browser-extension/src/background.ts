import type {
  CrawlListingsMessage,
  CrawlProgressMessage,
  ExtensionMessage,
  ExtractCurrentMessage,
  ImportMessage,
  ImportOutcome,
  ImportResponseMessage,
  VisibleListing,
} from './types';

export interface Configuration {
  apiUrl?: string;
  token?: string;
  tokenType?: 'bearer' | 'pairing';
}

const cancelledSourceTabs = new Set<number>();

function failure(error: unknown): string {
  return error instanceof Error && error.message
    ? error.message
    : 'Unbekannter Fehler';
}

function apiUnavailable(apiUrl: string, error: unknown): string {
  return `API nicht erreichbar (${apiUrl}): ${failure(error)}. API-Adresse, Server und Host-Berechtigung prüfen.`;
}

async function responseProblem(response: Response): Promise<string> {
  const body = await response.text();
  try {
    const problem = JSON.parse(body) as { detail?: string; title?: string };
    return `${response.status}: ${problem.detail ?? problem.title ?? response.statusText}`;
  } catch {
    return `${response.status}: ${body.slice(0, 180) || response.statusText}`;
  }
}

export async function importVisibleListings(
  listings: VisibleListing[],
  config: Configuration,
  fetchImpl: typeof fetch = fetch,
): Promise<ImportResponseMessage> {
  if (!config.apiUrl || !config.token) {
    return { imported: 0, results: [], error: 'Erweiterung zuerst konfigurieren' };
  }

  const apiUrl = config.apiUrl.replace(/\/$/, '');
  const authorization: Record<string, string> = config.tokenType === 'pairing'
    ? { 'X-Extension-Pairing': config.token }
    : { Authorization: `Bearer ${config.token}` };
  let imported = 0;
  let imageFailures = 0;
  const results: ImportOutcome[] = [];

  for (const listing of listings) {
    let response: Response;
    try {
      response = await fetchImpl(`${apiUrl}/api/v1/imports/browser`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': `${listing.externalId}:${listing.rawData.capturedAt}`,
          ...authorization,
        },
        body: JSON.stringify(listing),
      });
    } catch (error) {
      return { imported, results, imageFailures, error: apiUnavailable(apiUrl, error) };
    }

    if (!response.ok) {
      return { imported, results, imageFailures, error: await responseProblem(response) };
    }

    const result = await response.json() as {
      listing: {
        id: string;
        dealScore: number | null;
        riskScore: number | null;
        dataQualityScore: number | null;
      };
      snapshotCreated: boolean;
    };
    results.push({
      externalId: listing.externalId,
      listingId: result.listing.id,
      snapshotCreated: result.snapshotCreated,
      dealScore: result.listing.dealScore,
      riskScore: result.listing.riskScore,
      dataQualityScore: result.listing.dataQualityScore,
    });
    imported += 1;

    const imageUrls = listing.rawData.imageUrls ?? [];
    if (result.snapshotCreated && imageUrls.length) {
      try {
        const imageResponse = await fetchImpl(
          `${apiUrl}/api/v1/listings/${encodeURIComponent(result.listing.id)}/images`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...authorization,
            },
            body: JSON.stringify({ sourceUrls: imageUrls }),
          },
        );
        if (!imageResponse.ok) imageFailures += 1;
      } catch {
        imageFailures += 1;
      }
    }
  }

  return { imported, results, imageFailures };
}

async function handleImport(message: ImportMessage): Promise<ImportResponseMessage> {
  const [shared, secrets] = await Promise.all([
    chrome.storage.sync.get(['apiUrl', 'tokenType']),
    chrome.storage.local.get(['token']),
  ]);
  return importVisibleListings(message.listings, { ...shared, ...secrets } as Configuration);
}

async function configuredConnection(): Promise<Configuration> {
  const [shared, secrets] = await Promise.all([
    chrome.storage.sync.get(['apiUrl', 'tokenType']),
    chrome.storage.local.get(['token']),
  ]);
  return { ...shared, ...secrets } as Configuration;
}

async function waitForTab(tabId: number, timeoutMs = 25_000): Promise<void> {
  const current = await chrome.tabs.get(tabId);
  if (current.status === 'complete') return;
  await new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      reject(new Error('Zeitüberschreitung beim Laden der Angebotsseite'));
    }, timeoutMs);
    const listener = (updatedId: number, change: { status?: string }): void => {
      if (updatedId !== tabId || change.status !== 'complete') return;
      clearTimeout(timeout);
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    };
    chrome.tabs.onUpdated.addListener(listener);
  });
}

async function progress(tabId: number | undefined, value: CrawlProgressMessage): Promise<void> {
  if (tabId === undefined) return;
  await chrome.tabs.sendMessage(tabId, value).catch(() => undefined);
}

async function crawlListings(
  message: CrawlListingsMessage,
  sourceTabId: number | undefined,
): Promise<ImportResponseMessage> {
  const candidates = message.candidates.slice(0, 50);
  const sessionId = crypto.randomUUID();
  const config = await configuredConnection();
  const combined: ImportResponseMessage = { imported: 0, results: [], imageFailures: 0 };
  if (sourceTabId !== undefined) cancelledSourceTabs.delete(sourceTabId);

  for (let index = 0; index < candidates.length; index += 1) {
    if (sourceTabId !== undefined && cancelledSourceTabs.has(sourceTabId)) {
      combined.error = 'Vom Nutzer beendet';
      break;
    }
    const candidate = candidates[index];
    const base = {
      type: 'CRAWL_PROGRESS' as const,
      sessionId,
      current: index + 1,
      total: candidates.length,
      title: candidate.title,
      url: candidate.url,
    };
    await progress(sourceTabId, { ...base, status: 'opening' });
    let tabId: number | undefined;
    try {
      const tab = await chrome.tabs.create({ url: candidate.url, active: false });
      tabId = tab.id;
      if (tabId === undefined) throw new Error('Temporärer Browser-Tab konnte nicht erstellt werden');
      await waitForTab(tabId);
      await progress(sourceTabId, { ...base, status: 'extracting' });
      let listing: VisibleListing | null;
      try {
        listing = await chrome.tabs.sendMessage<ExtractCurrentMessage, VisibleListing | null>(
          tabId,
          { type: 'EXTRACT_CURRENT_LISTING' },
        );
      } catch {
        await chrome.scripting.executeScript({ target: { tabId }, files: ['content.js'] });
        listing = await chrome.tabs.sendMessage<ExtractCurrentMessage, VisibleListing | null>(
          tabId,
          { type: 'EXTRACT_CURRENT_LISTING' },
        );
      }
      if (!listing) {
        await progress(sourceTabId, { ...base, status: 'skipped', detail: 'Kein vollständiges Angebot erkannt' });
        continue;
      }
      listing.rawData = {
        ...listing.rawData,
        crawlSessionId: sessionId,
        crawlPosition: index + 1,
        crawlTotal: candidates.length,
      };
      await progress(sourceTabId, { ...base, status: 'saving' });
      const imported = await importVisibleListings([listing], config);
      combined.imported += imported.imported;
      combined.results.push(...imported.results);
      combined.imageFailures = (combined.imageFailures ?? 0) + (imported.imageFailures ?? 0);
      if (imported.error) {
        await progress(sourceTabId, { ...base, status: 'error', detail: imported.error });
      } else {
        await progress(sourceTabId, { ...base, status: 'saved' });
      }
    } catch (error) {
      await progress(sourceTabId, { ...base, status: 'error', detail: failure(error) });
    } finally {
      if (tabId !== undefined) await chrome.tabs.remove(tabId).catch(() => undefined);
    }
  }

  await progress(sourceTabId, {
    type: 'CRAWL_PROGRESS',
    sessionId,
    current: candidates.length,
    total: candidates.length,
    title: '',
    url: '',
    status: 'complete',
    detail: combined.error ?? `${combined.imported} von ${candidates.length} Angeboten gespeichert`,
  });
  if (sourceTabId !== undefined) cancelledSourceTabs.delete(sourceTabId);
  return combined;
}

if (typeof chrome !== 'undefined') {
  chrome.runtime.onMessage.addListener((message: ExtensionMessage, sender, sendResponse) => {
    if (message.type === 'CANCEL_CRAWL') {
      if (sender.tab?.id !== undefined) cancelledSourceTabs.add(sender.tab.id);
      sendResponse(true);
      return false;
    }
    const operation = message.type === 'IMPORT_VISIBLE_LISTINGS'
      ? handleImport(message)
      : message.type === 'CRAWL_LISTINGS'
        ? crawlListings(message, sender.tab?.id)
        : null;
    if (!operation) return false;
    void operation.then(
      sendResponse,
      (error: unknown) => sendResponse({
        imported: 0,
        results: [],
        error: `Erweiterungsfehler: ${failure(error)}`,
      } satisfies ImportResponseMessage),
    );
    return true;
  });
}
