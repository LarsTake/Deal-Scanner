import type { ImportMessage } from './types';

interface Configuration { apiUrl?: string; token?: string; tokenType?: 'bearer' | 'pairing' }

chrome.runtime.onMessage.addListener((message: ImportMessage, _sender, sendResponse) => {
  if (message.type !== 'IMPORT_VISIBLE_LISTINGS') return false;
  void (async () => {
    const [shared, secrets] = await Promise.all([
      chrome.storage.sync.get(['apiUrl', 'tokenType']),
      chrome.storage.local.get(['token']),
    ]);
    const config = { ...shared, ...secrets } as Configuration;
    if (!config.apiUrl || !config.token) { sendResponse({ imported: 0, error: 'Erweiterung zuerst konfigurieren' }); return; }
    let imported = 0;
    for (const listing of message.listings) {
      const response = await fetch(`${config.apiUrl.replace(/\/$/, '')}/api/v1/imports/browser`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json', 'Idempotency-Key': `${listing.externalId}:${listing.rawData.capturedAt}`,
          ...(config.tokenType === 'pairing' ? { 'X-Extension-Pairing': config.token } : { Authorization: `Bearer ${config.token}` }),
        },
        body: JSON.stringify(listing),
      });
      if (!response.ok) { const body = await response.text(); sendResponse({ imported, error: body.slice(0, 180) }); return; }
      const result = await response.json() as { listing: { id: string }; snapshotCreated: boolean };
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
          const body = await imageResponse.text();
          sendResponse({ imported: imported + 1, error: `Angebot importiert, Bildimport fehlgeschlagen: ${body.slice(0, 120)}` });
          return;
        }
      }
      imported += 1;
    }
    sendResponse({ imported });
  })();
  return true;
});
