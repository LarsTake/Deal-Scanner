import type {
  AnalysisJob,
  FeedbackCreate,
  ListingDetail,
  ListingEvaluation,
  ListingImage,
  ListingPage,
  MailImport,
  Notification,
  ManualImport,
  ProductPage,
  ProviderConfiguration,
  ProviderConfigurationUpsert,
  ProviderSyncRunPage,
  PriceObservation,
  SearchProfile,
  SearchProfileCreate,
  SystemStatus,
  Worker,
} from '@deal-scanner/contracts';

export interface ClientOptions {
  baseUrl: string;
  token?: () => Promise<string | null>;
  developmentUserId?: string;
}

export class ApiProblemError extends Error {
  constructor(
    readonly status: number,
    readonly problem: unknown,
    detail: string,
  ) {
    super(`[${status}] ${detail}`);
    this.name = 'ApiProblemError';
  }
}

export class DealScannerClient {
  constructor(private readonly options: ClientOptions) {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const token = await this.options.token?.();
    const response = await fetch(`${this.options.baseUrl.replace(/\/$/, '')}/api/v1${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(this.options.developmentUserId
          ? { 'X-Development-User': this.options.developmentUserId }
          : {}),
        ...init.headers,
      },
    });
    if (!response.ok) {
      const problem = (await response.json().catch(() => ({}))) as { detail?: unknown };
      throw new ApiProblemError(
        response.status,
        problem,
        typeof problem.detail === 'string' ? problem.detail : 'API request failed',
      );
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  systemStatus(): Promise<SystemStatus> {
    return this.request('/system/status');
  }

  listings(
    cursor?: string,
    view: 'all' | 'new' | 'favorites' | 'hidden' = 'all',
  ): Promise<ListingPage> {
    const query = new URLSearchParams({ view });
    if (cursor) query.set('cursor', cursor);
    return this.request(`/listings?${query.toString()}`);
  }

  listing(listingId: string): Promise<ListingDetail> {
    return this.request(`/listings/${encodeURIComponent(listingId)}`);
  }

  listingImages(listingId: string): Promise<ListingImage[]> {
    return this.request(`/listings/${encodeURIComponent(listingId)}/images`);
  }

  async imageObjectUrl(imageId: string): Promise<string> {
    const access = await this.request<{ url: string }>(
      `/listing-images/${encodeURIComponent(imageId)}/access`,
    );
    const token = await this.options.token?.();
    const url = access.url.startsWith('http')
      ? access.url
      : `${this.options.baseUrl.replace(/\/$/, '')}${access.url}`;
    const response = await fetch(url, {
      headers: access.url.startsWith('http')
        ? {}
        : {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(this.options.developmentUserId
              ? { 'X-Development-User': this.options.developmentUserId }
              : {}),
          },
    });
    if (!response.ok) throw new Error(`Bild konnte nicht geladen werden (${response.status})`);
    return URL.createObjectURL(await response.blob());
  }

  evaluateListing(listingId: string): Promise<ListingEvaluation> {
    return this.request(`/listings/${encodeURIComponent(listingId)}/evaluate`, { method: 'POST' });
  }

  reanalyzeListing(listingId: string): Promise<AnalysisJob> {
    return this.request(`/listings/${encodeURIComponent(listingId)}/reanalyze`, { method: 'POST' });
  }

  searchProfiles(): Promise<SearchProfile[]> {
    return this.request('/search-profiles');
  }

  createSearchProfile(profile: SearchProfileCreate): Promise<SearchProfile> {
    return this.request('/search-profiles', { method: 'POST', body: JSON.stringify(profile) });
  }

  updateSearchProfile(profileId: string, profile: SearchProfileCreate): Promise<SearchProfile> {
    return this.request(`/search-profiles/${encodeURIComponent(profileId)}`, {
      method: 'PUT',
      body: JSON.stringify(profile),
    });
  }

  deleteSearchProfile(profileId: string): Promise<void> {
    return this.request(`/search-profiles/${encodeURIComponent(profileId)}`, { method: 'DELETE' });
  }

  workers(): Promise<Worker[]> {
    return this.request('/workers');
  }

  jobs(status?: string): Promise<AnalysisJob[]> {
    return this.request(`/jobs${status ? `?status=${encodeURIComponent(status)}` : ''}`);
  }

  notifications(): Promise<Notification[]> {
    return this.request('/notifications');
  }

  markNotificationDelivered(notificationId: string): Promise<void> {
    return this.request(`/notifications/${encodeURIComponent(notificationId)}/delivered`, { method: 'POST' });
  }

  products(): Promise<ProductPage> {
    return this.request('/products');
  }

  priceObservations(canonicalProductId?: string): Promise<PriceObservation[]> {
    return this.request(
      `/price-observations${canonicalProductId ? `?canonicalProductId=${encodeURIComponent(canonicalProductId)}` : ''}`,
    );
  }

  providerSyncRuns(): Promise<ProviderSyncRunPage> {
    return this.request('/provider-sync-runs');
  }

  providerConfigurations(): Promise<ProviderConfiguration[]> {
    return this.request('/provider-configurations');
  }

  configureProvider(
    provider: 'ebay' | 'kleinanzeigenEmail' | 'browser' | 'manual',
    configuration: ProviderConfigurationUpsert,
  ): Promise<ProviderConfiguration> {
    return this.request(`/provider-configurations/${encodeURIComponent(provider)}`, {
      method: 'PUT',
      body: JSON.stringify(configuration),
    });
  }

  mailImports(): Promise<MailImport[]> {
    return this.request('/mail-imports');
  }

  importListing(listing: ManualImport, idempotencyKey: string = crypto.randomUUID()): Promise<unknown> {
    return this.request('/imports/manual', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(listing),
    });
  }

  createFeedback(
    listingId: string,
    feedback: FeedbackCreate,
  ): Promise<{ id: string; status: string; version: number }> {
    return this.request(`/listings/${encodeURIComponent(listingId)}/feedback`, {
      method: 'POST',
      body: JSON.stringify(feedback),
    });
  }
}

export type * from '@deal-scanner/contracts';
