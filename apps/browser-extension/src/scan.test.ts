import { describe, expect, it } from 'vitest';
import { createScan, detailStep, marketplaceUrl, searchStep } from './scan';

const search = 'https://www.kleinanzeigen.de/s-computer/k0';
const offer = (id: number) => `https://www.kleinanzeigen.de/s-anzeige/pc/${id}-228-1234`;
const options = { maxPages: 2, maxListings: 10, delaySeconds: 3 };

describe('bounded article-by-article traversal', () => {
  it('visits details in order, follows the next results page and deduplicates listings', () => {
    let state = searchStep(createScan(search, options), [offer(100), offer(101), offer(100)], `${search}?page=2`);
    expect(state.currentUrl).toBe(offer(100));
    state = detailStep(state, 1);
    expect(state.currentUrl).toBe(offer(101));
    state = detailStep(state, 1);
    expect(state).toMatchObject({ phase: 'search', currentUrl: `${search}?page=2`, imported: 2 });
    state = searchStep(state, [offer(101), offer(102)], `${search}?page=3`);
    expect(state.pending).toEqual([offer(102)]);
    state = detailStep(state, 1);
    expect(state.status).toBe('done');
    expect(state.imported).toBe(3);
    expect(state.visitedPages).toHaveLength(2);
  });

  it('enforces the listing limit even if more cards and pages exist', () => {
    let state = searchStep(createScan(search, { ...options, maxListings: 1 }), [offer(100), offer(101)], `${search}?page=2`);
    expect(state.pending).toEqual([offer(100)]);
    state = detailStep(state, 1);
    expect(state.status).toBe('done');
    expect(state.visitedListings).toHaveLength(1);
  });

  it('ends at the final page or a pagination loop', () => {
    let state = searchStep(createScan(search, options), [offer(100)], search);
    expect(detailStep(state, 1).status).toBe('done');
    state = searchStep(createScan(search, options), [offer(100)], null);
    expect(detailStep(state, 1).status).toBe('done');
  });

  it('rejects external hosts, disguised host names and unreasonable limits', () => {
    expect(() => marketplaceUrl('https://evilkleinanzeigen.de/s-anzeige/pc/100')).toThrow();
    expect(() => searchStep(createScan(search, options), [offer(100)], 'https://example.com')).toThrow();
    expect(() => createScan(search, { ...options, maxPages: 21 })).toThrow();
    expect(() => createScan(search, { ...options, delaySeconds: 0 })).toThrow();
    expect(() => createScan(search, { ...options, maxListings: 1.5 })).toThrow();
  });
});
