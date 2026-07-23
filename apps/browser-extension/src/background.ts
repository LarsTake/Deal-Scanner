import type { ImportMessage, ImportOutcome, ImportResponseMessage } from './types';

interface Configuration { apiUrl?: string; token?: string; tokenType?: 'bearer' | 'pairing' }

chrome.runtime.onMessage.addListener((message: ImportMessage, _sender, sendResponse) => {
  if (message.type !== 'IMPORT_VISIBLE_LISTINGS') return false;
  void (async () => {
    const [shared, secrets] = await Promise.all([
      chrome.storage.sync.get(['apiUrl', 'tokenType']),
      chrome.storage.local.get(['token']),
    ]);
    const config = { ...shared, ...secrets } as Configuration;
    if (!config.apiUrl || !config.token) {
      sendResponse({ imported: 0, results: [], error: 'Erweiterung zuerst konfigurieren' } satisfies ImportResponseMessage);
      return;
    }
    let imported = 0;
    let imageFailures = 0;
    const results: ImportOutcome[] = [];
    for (const listing of message.listings) {
      const response = await fetch(`${config.apiUrl.replace(/\/$/, '')}/api/v1/imports/browser`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json', 'Idempotency-Key': `${listing.externalId}:${listing.rawData.capturedAt}`,
          ...(config.tokenType === 'pairing' ? { 'X-Extension-Pairing': config.token } : { Authorization: `Bearer ${config.token}` }),
        },
        body: JSON.stringify(listing),
      });
      if (!response.ok) {
        const body = await response.text();
        sendResponse({ imported, results, error: body.slice(0, 180) } satisfies ImportResponseMessage);
        return;
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
        const imageResponse = await fetch(
          `${config.apiUrl.replace(/\/$/, '')}/api/v1/listings/${encodeURIComponent(result.listing.id)}/images`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(config.tokenType === 'pairing' ? { 'X-Extension-Pairing': config.token } : { Authorization: `Bearer ${config.token}` }),
            },
            body: JSON.stringify({ sourceUrls: imageUrls }),
          },
        );
        if (!imageResponse.ok) {
          imageFailures += 1;
        }
      }
    }
    sendResponse({ imported, results, imageFailures } satisfies ImportResponseMessage);
  })();
  return true;
});
