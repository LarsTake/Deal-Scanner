export interface VisibleListing {
  platform: string;
  externalId: string;
  url: string;
  title: string;
  description: string;
  price: string;
  currency: string;
  location?: string;
  seller?: {
    externalId: string;
    displayName?: string;
    accountAgeText?: string;
    ratingText?: string;
    location?: string;
    rawData: { source: 'visibleBrowserPage' };
  };
  categoryProfile: string;
  rawData: {
    source: 'visibleBrowserPage';
    capturedAt: string;
    imageUrls?: string[];
    pageHost?: string;
    extractionMethod?: string;
    crawlSessionId?: string;
    crawlPosition?: number;
    crawlTotal?: number;
  };
  providerVersion: string;
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
  imageFailures?: number;
  error?: string;
}

export interface CrawlCandidate {
  url: string;
  title: string;
}

export interface CrawlListingsMessage {
  type: 'CRAWL_LISTINGS';
  candidates: CrawlCandidate[];
}

export interface ExtractCurrentMessage {
  type: 'EXTRACT_CURRENT_LISTING';
}

export interface ShowPanelMessage {
  type: 'SHOW_PANEL';
}

export interface CancelCrawlMessage {
  type: 'CANCEL_CRAWL';
}

export interface CrawlProgressMessage {
  type: 'CRAWL_PROGRESS';
  sessionId: string;
  current: number;
  total: number;
  title: string;
  url: string;
  status: 'opening' | 'extracting' | 'saving' | 'saved' | 'skipped' | 'error' | 'complete';
  detail?: string;
}

export type ExtensionMessage =
  | ImportMessage
  | CrawlListingsMessage
  | ExtractCurrentMessage
  | ShowPanelMessage
  | CancelCrawlMessage
  | CrawlProgressMessage;
