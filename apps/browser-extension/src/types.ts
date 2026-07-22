export interface VisibleListing {
  platform: 'kleinanzeigen';
  externalId: string;
  url: string;
  title: string;
  description: string;
  price: string;
  currency: 'EUR';
  location?: string;
  categoryProfile: 'general';
  rawData: { source: 'visibleBrowserPage'; capturedAt: string; imageUrls?: string[] };
  providerVersion: 'browser-extension-v1';
}

export interface ImportMessage {
  type: 'IMPORT_VISIBLE_LISTINGS';
  listings: VisibleListing[];
}
