import { Injectable } from '@angular/core';
import type { ListingSummary } from '@deal-scanner/contracts';
import type Database from '@tauri-apps/plugin-sql';

export type OutboxKind = 'feedback' | 'import';

export interface OutboxItem {
  id: string;
  kind: OutboxKind;
  aggregateId: string | null;
  baseVersion: number | null;
  payload: unknown;
  status: 'pending' | 'conflict';
}

export function isConflictError(error: unknown): boolean {
  return error instanceof Error && /\b409\b|conflict/i.test(error.message);
}

export async function processOutboxItems(
  items: OutboxItem[],
  sender: (item: OutboxItem) => Promise<void>,
  delivered: (item: OutboxItem) => Promise<void>,
  conflicted: (item: OutboxItem) => Promise<void>,
): Promise<void> {
  for (const item of items) {
    if (item.status !== 'pending') continue;
    try {
      await sender(item);
      await delivered(item);
    } catch (error) {
      if (isConflictError(error)) await conflicted(item);
    }
  }
}

@Injectable({ providedIn: 'root' })
export class OfflineCacheService {
  private database: Database | null = null;

  async initialize(): Promise<void> {
    if (!('__TAURI_INTERNALS__' in window)) return;
    const { default: Database } = await import('@tauri-apps/plugin-sql');
    this.database = await Database.load('sqlite:deal-scanner-cache.db');
    await this.database.execute(
      'CREATE TABLE IF NOT EXISTS listing_cache (id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL, cached_at TEXT NOT NULL)',
    );
    await this.database.execute(
      "CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, kind TEXT NOT NULL, aggregate_id TEXT, base_version INTEGER, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)",
    );
  }

  async cacheListings(listings: ListingSummary[]): Promise<void> {
    if (!this.database) return;
    for (const listing of listings) {
      await this.database.execute(
        'INSERT OR REPLACE INTO listing_cache (id, version, payload, cached_at) VALUES ($1, $2, $3, $4)',
        [listing.id, listing.version, JSON.stringify(listing), new Date().toISOString()],
      );
    }
  }

  async readListings(): Promise<ListingSummary[]> {
    if (!this.database) return [];
    const rows = await this.database.select<Array<{ payload: string }>>(
      'SELECT payload FROM listing_cache ORDER BY cached_at DESC',
    );
    return rows.map((row) => JSON.parse(row.payload) as ListingSummary);
  }

  async enqueue(
    kind: OutboxKind,
    payload: unknown,
    aggregateId: string | null = null,
    baseVersion: number | null = null,
  ): Promise<string> {
    const id = crypto.randomUUID();
    if (!this.database) throw new Error('Offline-Outbox ist nur in der Desktop-App verfügbar.');
    await this.database.execute(
      'INSERT INTO outbox (id, kind, aggregate_id, base_version, payload, status, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7)',
      [id, kind, aggregateId, baseVersion, JSON.stringify(payload), 'pending', new Date().toISOString()],
    );
    return id;
  }

  async pending(): Promise<OutboxItem[]> {
    if (!this.database) return [];
    const rows = await this.database.select<
      Array<{
        id: string;
        kind: OutboxKind;
        aggregate_id: string | null;
        base_version: number | null;
        payload: string;
        status: 'pending' | 'conflict';
      }>
    >('SELECT id, kind, aggregate_id, base_version, payload, status FROM outbox ORDER BY created_at');
    return rows.map((row) => ({
      id: row.id,
      kind: row.kind,
      aggregateId: row.aggregate_id,
      baseVersion: row.base_version,
      payload: JSON.parse(row.payload),
      status: row.status,
    }));
  }

  async markConflict(id: string): Promise<void> {
    await this.database?.execute("UPDATE outbox SET status = 'conflict' WHERE id = $1", [id]);
  }

  async retry(id: string, payload: unknown, baseVersion: number | null): Promise<void> {
    await this.database?.execute(
      "UPDATE outbox SET payload = $1, base_version = $2, status = 'pending' WHERE id = $3",
      [JSON.stringify(payload), baseVersion, id],
    );
  }

  async discard(id: string): Promise<void> {
    await this.database?.execute('DELETE FROM outbox WHERE id = $1', [id]);
  }

  async synchronize(sender: (item: OutboxItem) => Promise<void>): Promise<void> {
    await processOutboxItems(
      await this.pending(),
      sender,
      async (item) => this.discard(item.id),
      async (item) => this.markConflict(item.id),
    );
  }
}
