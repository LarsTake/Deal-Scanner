import type {
  AnalysisJob,
  CsvImport,
  ExtensionConnection,
  ExtensionConnectionCreate,
  ExtensionConnectionCreated,
  FeedbackCreate,
  ListingDetail,
  ListingEvaluation,
  ListingImage,
  ListingNoteUpdate,
  ListingPage,
  MailImport,
  ManualImport,
  Notification,
  paths,
  PriceObservation,
  ProductPage,
  ProviderConfiguration,
  ProviderConfigurationUpsert,
  ProviderSyncRunPage,
  SearchProfile,
  SearchProfileCreate,
  SystemStatus,
  Worker,
} from '@deal-scanner/contracts';
import createClient, { type Client } from 'openapi-fetch';

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

type ApiResult<T> = {
  data?: T;
  error?: unknown;
  response: Response;
};

export type GeneratedDealScannerClient = Client<paths>;

/** Full generated transport for endpoints that do not need an ergonomic facade method. */
export function createGeneratedDealScannerClient(
  options: ClientOptions,
): GeneratedDealScannerClient {
  const client = createClient<paths>({
    baseUrl: options.baseUrl.replace(/\/$/, ''),
  });
  client.use({
    onRequest: async ({ request }) => {
      const token = await options.token?.();
      if (token) request.headers.set('Authorization', `Bearer ${token}`);
      if (options.developmentUserId) {
        request.headers.set('X-Development-User', options.developmentUserId);
      }
      return request;
    },
  });
  return client;
}

/**
 * Ergonomic Angular-facing facade over the OpenAPI-generated `paths` contract.
 * Every verb, route, parameter and body below is checked against generated.ts.
 */
export class DealScannerClient {
  private readonly client: Client<paths>;

  constructor(private readonly options: ClientOptions) {
    this.client = createGeneratedDealScannerClient(options);
  }

  private unwrap<T>(result: ApiResult<T>): T {
    if (result.error !== undefined || !result.response.ok || result.data === undefined) {
      throw this.problem(result.response, result.error);
    }
    return result.data;
  }

  private unwrapVoid(result: ApiResult<unknown>): void {
    if (result.error !== undefined || !result.response.ok) {
      throw this.problem(result.response, result.error);
    }
  }

  private problem(response: Response, problem: unknown): ApiProblemError {
    const detail =
      typeof problem === 'object' && problem !== null && 'detail' in problem
        ? (problem as { detail?: unknown }).detail
        : undefined;
    return new ApiProblemError(
      response.status,
      problem,
      typeof detail === 'string' ? detail : 'API request failed',
    );
  }

  async systemStatus(): Promise<SystemStatus> {
    return this.unwrap(await this.client.GET('/api/v1/system/status'));
  }

  async listings(
    cursor?: string,
    view: 'all' | 'new' | 'favorites' | 'hidden' | 'top_rated' = 'all',
    platform?: string,
    category?: string,
    q?: string,
    importedFrom?: string,
    importedTo?: string,
  ): Promise<ListingPage> {
    return this.unwrap(
      await this.client.GET('/api/v1/listings', {
        params: {
          query: {
            cursor,
            view,
            platform,
            category,
            q,
            imported_from: importedFrom,
            imported_to: importedTo,
          },
        },
      }),
    );
  }

  async listing(listingId: string): Promise<ListingDetail> {
    return this.unwrap(
      await this.client.GET('/api/v1/listings/{listing_id}', {
        params: { path: { listing_id: listingId } },
      }),
    );
  }

  async updateListingNote(
    listingId: string,
    payload: ListingNoteUpdate,
  ): Promise<ListingDetail> {
    return this.unwrap(
      await this.client.PATCH('/api/v1/listings/{listing_id}/note', {
        params: { path: { listing_id: listingId } },
        body: payload,
      }),
    );
  }

  async listingImages(listingId: string): Promise<ListingImage[]> {
    return this.unwrap(
      await this.client.GET('/api/v1/listings/{listing_id}/images', {
        params: { path: { listing_id: listingId } },
      }),
    );
  }

  async imageObjectUrl(imageId: string): Promise<string> {
    const access = this.unwrap(
      await this.client.GET('/api/v1/listing-images/{image_id}/access', {
        params: { path: { image_id: imageId } },
      }),
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

  async evaluateListing(listingId: string): Promise<ListingEvaluation> {
    return this.unwrap(
      await this.client.POST('/api/v1/listings/{listing_id}/evaluate', {
        params: { path: { listing_id: listingId } },
      }),
    );
  }

  async reanalyzeListing(listingId: string): Promise<AnalysisJob> {
    return this.unwrap(
      await this.client.POST('/api/v1/listings/{listing_id}/reanalyze', {
        params: { path: { listing_id: listingId } },
      }),
    );
  }

  async searchProfiles(): Promise<SearchProfile[]> {
    return this.unwrap(await this.client.GET('/api/v1/search-profiles'));
  }

  async createSearchProfile(profile: SearchProfileCreate): Promise<SearchProfile> {
    return this.unwrap(
      await this.client.POST('/api/v1/search-profiles', { body: profile }),
    );
  }

  async updateSearchProfile(
    profileId: string,
    profile: SearchProfileCreate,
  ): Promise<SearchProfile> {
    return this.unwrap(
      await this.client.PUT('/api/v1/search-profiles/{profile_id}', {
        params: { path: { profile_id: profileId } },
        body: profile,
      }),
    );
  }

  async deleteSearchProfile(profileId: string): Promise<void> {
    this.unwrapVoid(
      await this.client.DELETE('/api/v1/search-profiles/{profile_id}', {
        params: { path: { profile_id: profileId } },
      }),
    );
  }

  async workers(): Promise<Worker[]> {
    return this.unwrap(await this.client.GET('/api/v1/workers'));
  }

  async jobs(status?: string): Promise<AnalysisJob[]> {
    return this.unwrap(
      await this.client.GET('/api/v1/jobs', { params: { query: { status } } }),
    );
  }

  async notifications(): Promise<Notification[]> {
    return this.unwrap(await this.client.GET('/api/v1/notifications'));
  }

  async markNotificationDelivered(notificationId: string): Promise<void> {
    this.unwrapVoid(
      await this.client.POST('/api/v1/notifications/{notification_id}/delivered', {
        params: { path: { notification_id: notificationId } },
      }),
    );
  }

  async products(): Promise<ProductPage> {
    return this.unwrap(await this.client.GET('/api/v1/products'));
  }

  async priceObservations(canonicalProductId?: string): Promise<PriceObservation[]> {
    return this.unwrap(
      await this.client.GET('/api/v1/price-observations', {
        params: { query: { canonicalProductId } },
      }),
    );
  }

  async importMarketDataCsv(filename: string, content: string): Promise<CsvImport> {
    const form = new FormData();
    form.append('file', new Blob([content], { type: 'text/csv;charset=utf-8' }), filename);
    return this.unwrap(
      await this.client.POST('/api/v1/market-data/imports/csv', {
        body: { file: filename },
        bodySerializer: () => form,
      }),
    );
  }

  async providerSyncRuns(): Promise<ProviderSyncRunPage> {
    return this.unwrap(await this.client.GET('/api/v1/provider-sync-runs'));
  }

  async providerConfigurations(): Promise<ProviderConfiguration[]> {
    return this.unwrap(await this.client.GET('/api/v1/provider-configurations'));
  }

  async extensionConnections(): Promise<ExtensionConnection[]> {
    return this.unwrap(await this.client.GET('/api/v1/extension/connections'));
  }

  async createExtensionConnection(
    connection: ExtensionConnectionCreate,
  ): Promise<ExtensionConnectionCreated> {
    return this.unwrap(
      await this.client.POST('/api/v1/extension/connections', { body: connection }),
    );
  }

  async revokeExtensionConnection(connectionId: string): Promise<void> {
    this.unwrapVoid(
      await this.client.DELETE('/api/v1/extension/connections/{connection_id}', {
        params: { path: { connection_id: connectionId } },
      }),
    );
  }

  async configureProvider(
    provider: 'ebay' | 'kleinanzeigenEmail' | 'browser' | 'manual' | 'ollama',
    configuration: ProviderConfigurationUpsert,
  ): Promise<ProviderConfiguration> {
    return this.unwrap(
      await this.client.PUT('/api/v1/provider-configurations/{provider}', {
        params: { path: { provider } },
        body: configuration,
      }),
    );
  }

  async mailImports(): Promise<MailImport[]> {
    return this.unwrap(await this.client.GET('/api/v1/mail-imports'));
  }

  async importListing(
    listing: ManualImport,
    idempotencyKey: string = crypto.randomUUID(),
  ): Promise<unknown> {
    return this.unwrap(
      await this.client.POST('/api/v1/imports/manual', {
        params: { header: { 'Idempotency-Key': idempotencyKey } },
        body: listing,
      }),
    );
  }

  async createFeedback(
    listingId: string,
    feedback: FeedbackCreate,
  ): Promise<{ id: string; status: string; version: number }> {
    const result = this.unwrap(
      await this.client.POST('/api/v1/listings/{listing_id}/feedback', {
        params: { path: { listing_id: listingId } },
        body: feedback,
      }),
    );
    return {
      id: String(result.id),
      status: String(result.status),
      version: Number(result.version),
    };
  }
}

export type * from '@deal-scanner/contracts';
