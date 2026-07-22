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
});
