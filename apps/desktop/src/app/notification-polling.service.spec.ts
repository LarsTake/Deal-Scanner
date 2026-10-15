import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ApiService } from './api.service';
import type { DesktopNotificationService } from './desktop-notification.service';
import { NotificationPollingService } from './notification-polling.service';

describe('notification delivery', () => {
  beforeEach(() => localStorage.clear());

  it('bundles bursts and acknowledges all members only after successful native delivery', async () => {
    const items = Array.from({ length: 6 }, (_, i) => ({ id: String(i), reason: { title: `Offer ${i}` } }));
    const api = { notifications: vi.fn(async () => items), markNotificationDelivered: vi.fn(async () => undefined) };
    const desktop = { send: vi.fn(async (_title: string, _body: string) => true) };
    const service = new NotificationPollingService(api as unknown as ApiService, desktop as DesktopNotificationService);
    await (service as unknown as { poll(): Promise<void> }).poll();
    expect(desktop.send).toHaveBeenCalledOnce();
    expect(desktop.send.mock.calls[0][0]).toContain('6');
    expect(api.markNotificationDelivered).toHaveBeenCalledTimes(6);
    await (service as unknown as { poll(): Promise<void> }).poll();
    expect(desktop.send).toHaveBeenCalledOnce();
  });

  it('keeps failed native deliveries pending for a later attempt', async () => {
    const api = { notifications: vi.fn(async () => [{ id: 'one', reason: { title: 'Offer' } }]),
      markNotificationDelivered: vi.fn(async () => undefined) };
    const desktop = { send: vi.fn(async () => false) };
    const service = new NotificationPollingService(api as unknown as ApiService, desktop as DesktopNotificationService);
    await (service as unknown as { poll(): Promise<void> }).poll();
    expect(api.markNotificationDelivered).not.toHaveBeenCalled();
    expect(JSON.parse(localStorage.getItem('deal-scanner-seen-notifications') ?? '[]')).toEqual([]);
  });
});
