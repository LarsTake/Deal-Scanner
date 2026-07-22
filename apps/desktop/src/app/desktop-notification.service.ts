import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class DesktopNotificationService {
  async send(title: string, body: string): Promise<boolean> {
    if (!('__TAURI_INTERNALS__' in window)) return false;
    const { isPermissionGranted, requestPermission, sendNotification } = await import(
      '@tauri-apps/plugin-notification'
    );
    const granted = (await isPermissionGranted()) || (await requestPermission()) === 'granted';
    if (!granted) return false;
    sendNotification({ title, body });
    return true;
  }
}
