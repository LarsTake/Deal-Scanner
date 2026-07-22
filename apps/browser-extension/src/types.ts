export interface VisibleListing {
  platform: 'kleinanzeigen';
  externalId: string;
  url: string;
  title: string;
  description: string;
  price: string;
  currency: 'EUR';
  location?: string;
  seller?: {
    externalId: string;
    displayName?: string;
    accountAgeText?: string;
    ratingText?: string;
    location?: string;
    rawData: { source: 'visibleBrowserPage' };
  };
  categoryProfile: 'general';
  rawData: { source: 'visibleBrowserPage'; capturedAt: string; imageUrls?: string[] };
  providerVersion: 'browser-extension-v1';
}

export interface ImportMessage {
  type: 'IMPORT_VISIBLE_LISTINGS';
  listings: VisibleListing[];
}

export interface ImportOutcome {
  externalId: string;
  listingId: string;
  snapshotCreated: boolean;
  dealScore: number | null;
  riskScore: number | null;
  dataQualityScore: number | null;
}

export interface ImportResponseMessage {
  imported: number;
  results: ImportOutcome[];
  error?: string;
}
