import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiProblemError, DealScannerClient } from './index';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('DealScannerClient', () => {
  it('serializes generated route parameters and applies authentication headers', async () => {
    const fetchMock = vi.fn(async (request: Request) => {
      expect(request.url).toBe(
        'https://api.example.test/api/v1/listings?cursor=next%2Fpage&view=favorites',
      );
      expect(request.headers.get('Authorization')).toBe('Bearer test-token');
      expect(request.headers.get('X-Development-User')).toBe('development-user');
      return Response.json({ items: [], nextCursor: null });
    });
    vi.stubGlobal('fetch', fetchMock);
    const client = new DealScannerClient({
      baseUrl: 'https://api.example.test/',
      token: async () => 'test-token',
      developmentUserId: 'development-user',
    });

    await expect(client.listings('next/page', 'favorites')).resolves.toEqual({
      items: [],
      nextCursor: null,
    });
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('maps generated problem responses to ApiProblemError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json(
          { type: 'about:blank', title: 'Unauthorized', status: 401, detail: 'Token fehlt' },
          { status: 401 },
        ),
      ),
    );
    const client = new DealScannerClient({ baseUrl: 'https://api.example.test' });

    await expect(client.systemStatus()).rejects.toMatchObject({
      name: 'ApiProblemError',
      status: 401,
      message: '[401] Token fehlt',
    } satisfies Partial<ApiProblemError>);
  });

  it('updates a versioned manual listing note through the generated route', async () => {
    const fetchMock = vi.fn(async (request: Request) => {
      expect(request.method).toBe('PATCH');
      expect(request.url).toBe('https://api.example.test/api/v1/listings/listing-id/note');
      expect(await request.json()).toEqual({
        manualNote: 'Zustand vor Ort geprüft',
        baseListingVersion: 3,
      });
      return Response.json({
        id: 'listing-id',
        manualNote: 'Zustand vor Ort geprüft',
        version: 4,
      });
    });
    vi.stubGlobal('fetch', fetchMock);
    const client = new DealScannerClient({ baseUrl: 'https://api.example.test' });

    await expect(
      client.updateListingNote('listing-id', {
        manualNote: 'Zustand vor Ort geprüft',
        baseListingVersion: 3,
      }),
    ).resolves.toMatchObject({
      manualNote: 'Zustand vor Ort geprüft',
      version: 4,
    });
  });

  it('uploads market data through the generated multipart route', async () => {
    vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
      expect(request.url).toBe('https://api.example.test/api/v1/market-data/imports/csv');
      const form = await request.formData();
      const file = form.get('file');
      expect(file).toBeInstanceOf(File);
      expect((file as File).name).toBe('prices.csv');
      expect(await (file as File).text()).toContain('observedPrice');
      return Response.json({ rowsImported: 1, filename: 'prices.csv' }, { status: 201 });
    }));
    const client = new DealScannerClient({ baseUrl: 'https://api.example.test' });

    await expect(client.importMarketDataCsv('prices.csv', 'observedPrice\n100')).resolves.toEqual({
      rowsImported: 1,
      filename: 'prices.csv',
    });
  });

  it('creates and revokes an authenticated permanent extension connection', async () => {
    const fetchMock = vi.fn(async (request: Request) => {
      if (request.method === 'POST') {
        expect(request.url).toBe('https://api.example.test/api/v1/extension/connections');
        expect(await request.json()).toEqual({ displayName: 'Büro-Browser' });
        return Response.json(
          {
            id: 'connection-id',
            displayName: 'Büro-Browser',
            createdAt: '2026-07-23T12:00:00Z',
            token: 'device-token',
          },
          { status: 201 },
        );
      }
      expect(request.method).toBe('DELETE');
      expect(request.url).toBe(
        'https://api.example.test/api/v1/extension/connections/connection-id',
      );
      return new Response(null, { status: 204 });
    });
    vi.stubGlobal('fetch', fetchMock);
    const client = new DealScannerClient({ baseUrl: 'https://api.example.test' });

    await expect(
      client.createExtensionConnection({ displayName: 'Büro-Browser' }),
    ).resolves.toMatchObject({ token: 'device-token' });
    await expect(client.revokeExtensionConnection('connection-id')).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
