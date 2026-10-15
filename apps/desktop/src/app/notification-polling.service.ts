import { Injectable } from '@angular/core';

import { ApiService } from './api.service';
import { DesktopNotificationService } from './desktop-notification.service';

@Injectable({ providedIn: 'root' })
export class NotificationPollingService {
  private timer: ReturnType<typeof setInterval> | null = null;
  private polling = false;

  constructor(
    private readonly api: ApiService,
    private readonly desktop: DesktopNotificationService,
  ) {}

  start(): void {
    if (this.timer) return;
    void this.poll();
    this.timer = setInterval(() => void this.poll(), 60_000);
  }

  private async poll(): Promise<void> {
    if (this.polling) return;
    this.polling = true;
    try {
      const seen = new Set(JSON.parse(localStorage.getItem('deal-scanner-seen-notifications') ?? '[]') as string[]);
      const notifications = await this.api.notifications();
      const pending = [...notifications].reverse().filter((item) => !seen.has(item.id));
      const groups = pending.length > 5 ? [pending] : pending.map((item) => [item]);
      for (const group of groups) {
        const first = group[0];
        const title = group.length > 1 ? `${group.length} neue Deal-Scanner-Angebote`
          : String(first.reason['title'] ?? 'Neues Deal-Scanner-Angebot');
        const body = group.length > 1
          ? group.slice(0, 5).map((item) => String(item.reason['title'] ?? 'Angebot')).join(' · ')
          : first.reason['type'] === 'restock' ? String(first.reason['body'] ?? 'Wieder verfügbar')
          : `Deal ${String(first.reason['dealScore'])} · Risiko ${String(first.reason['riskScore'])}`;
        if (!await this.desktop.send(title, body)) continue;
        for (const notification of group) {
          await this.api.markNotificationDelivered(notification.id);
          seen.add(notification.id);
        }
        localStorage.setItem('deal-scanner-seen-notifications', JSON.stringify([...seen].slice(-500)));
      }
      localStorage.setItem('deal-scanner-seen-notifications', JSON.stringify([...seen].slice(-500)));
    } catch {
      // Offline and unauthenticated states are expected; the next interval retries.
    } finally { this.polling = false; }
  }
}
