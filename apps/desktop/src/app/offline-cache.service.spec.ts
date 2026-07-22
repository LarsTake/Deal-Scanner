import { describe, expect, it, vi } from 'vitest';

import { type OutboxItem, isConflictError, processOutboxItems } from './offline-cache.service';

const item = (id: string, status: OutboxItem['status'] = 'pending'): OutboxItem => ({
  id,
  kind: 'feedback',
  aggregateId: 'listing',
  baseVersion: 1,
  payload: {},
  status,
});

describe('offline outbox conflict handling', () => {
  it('recognizes version conflicts without classifying ordinary network errors as conflicts', () => {
    expect(isConflictError(new Error('[409] listing version conflict'))).toBe(true);
    expect(isConflictError(new Error('network unavailable'))).toBe(false);
  });

  it('deletes delivered entries, exposes conflicts, and keeps transient failures pending', async () => {
    const delivered = vi.fn(async () => undefined);
    const conflicted = vi.fn(async () => undefined);
    const sender = vi.fn(async (outbox: OutboxItem) => {
      if (outbox.id === 'conflict') throw new Error('[409] conflict');
      if (outbox.id === 'offline') throw new Error('network unavailable');
    });

    await processOutboxItems(
      [item('sent'), item('conflict'), item('offline'), item('already-conflicted', 'conflict')],
      sender,
      delivered,
      conflicted,
    );

    expect(delivered).toHaveBeenCalledOnce();
    expect(delivered).toHaveBeenCalledWith(expect.objectContaining({ id: 'sent' }));
    expect(conflicted).toHaveBeenCalledOnce();
    expect(conflicted).toHaveBeenCalledWith(expect.objectContaining({ id: 'conflict' }));
    expect(sender).toHaveBeenCalledTimes(3);
  });
});
