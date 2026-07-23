import { describe, expect, it, vi } from 'vitest';

import { importVisibleListings, type Configuration } from './background';
import type { VisibleListing } from './types';

const listing: VisibleListing = {
  platform: 'kleinanzeigen',
  externalId: '3462624376',
  url: 'https://www.kleinanzeigen.de/s-anzeige/gaming-pc/3462624376-228-1944',
  title: 'Gaming PC',
  description: 'RTX 4070',
  price: '900',
  currency: 'EUR',
  categoryProfile: 'general',
  rawData: {
    source: 'visibleBrowserPage',
    capturedAt: '2026-07-23T20:00:00.000Z',
    imageUrls: ['https://img.kleinanzeigen.de/example.jpg'],
  },
  providerVersion: 'browser-extension-v1',
};

const config: Configuration = {
  apiUrl: 'http://127.0.0.1:8000',
  token: 'device-token',
  tokenType: 'pairing',
};

describe('background import', () => {
  it('returns a response when the API fetch is rejected', async () => {
    const fetchMock = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });

    await expect(
      importVisibleListings([listing], config, fetchMock as typeof fetch),
    ).resolves.toMatchObject({
      imported: 0,
      results: [],
      error: expect.stringContaining('API nicht erreichbar'),
    });
  });

  it('keeps a successful listing import when only the image fetch fails', async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      if (String(input).endsWith('/images')) throw new TypeError('Failed to fetch');
      return Response.json({
        listing: {
          id: '00000000-0000-4000-8000-000000000001',
          dealScore: null,
          riskScore: null,
          dataQualityScore: null,
        },
        snapshotCreated: true,
      });
    });

    await expect(
      importVisibleListings([listing], config, fetchMock as typeof fetch),
    ).resolves.toMatchObject({
      imported: 1,
      imageFailures: 1,
      results: [
        {
          externalId: '3462624376',
          snapshotCreated: true,
        },
      ],
    });
  });

  it('returns structured API problem details instead of throwing', async () => {
    const fetchMock = vi.fn(async () => Response.json(
      { title: 'Request failed', detail: 'invalid or expired pairing token' },
      { status: 401 },
    ));

    await expect(
      importVisibleListings([listing], config, fetchMock as typeof fetch),
    ).resolves.toMatchObject({
      imported: 0,
      error: '401: invalid or expired pairing token',
    });
  });
});
