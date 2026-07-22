import { Injectable } from '@angular/core';

import { ApiService } from './api.service';
import { DesktopNotificationService } from './desktop-notification.service';

@Injectable({ providedIn: 'root' })
export class NotificationPollingService {
  private timer: ReturnType<typeof setInterval> | null = null;

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
    try {
      const seen = new Set(JSON.parse(localStorage.getItem('deal-scanner-seen-notifications') ?? '[]') as string[]);
      const notifications = await this.api.notifications();
      for (const notification of [...notifications].reverse()) {
        if (seen.has(notification.id)) continue;
        const title = String(notification.reason['title'] ?? 'Neues Deal-Scanner-Angebot');
        const deal = notification.reason['dealScore'];
        const risk = notification.reason['riskScore'];
        await this.desktop.send(title, `Deal ${String(deal)} · Risiko ${String(risk)}`);
        seen.add(notification.id);
      }
      localStorage.setItem('deal-scanner-seen-notifications', JSON.stringify([...seen].slice(-500)));
    } catch {
      // Offline and unauthenticated states are expected; the next interval retries.
    }
  }
}
