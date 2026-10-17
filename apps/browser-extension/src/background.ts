import type {
  ImportMessage,
  ImportOutcome,
  ImportResponseMessage,
  VisibleListing,
} from './types';
import { handleScanMessage, type ScanMessage } from './scan-background';

export interface Configuration {
  apiUrl?: string;
  token?: string;
  tokenType?: 'bearer' | 'pairing';
}

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
        signal: AbortSignal.timeout(25000),
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
            signal: AbortSignal.timeout(25000),
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

if (typeof chrome !== 'undefined') {
  chrome.runtime.onMessage.addListener((message: ImportMessage | ScanMessage, sender, sendResponse) => {
    if (!message || typeof message.type !== 'string') return false;
    if (message.type.startsWith('SCAN_')) {
      void handleScanMessage(message as ScanMessage, sender).then(sendResponse,
        (error: unknown) => sendResponse({ error: failure(error) }));
      return true;
    }
    if (message.type !== 'IMPORT_VISIBLE_LISTINGS') return false;
    void handleImport(message).then(
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
