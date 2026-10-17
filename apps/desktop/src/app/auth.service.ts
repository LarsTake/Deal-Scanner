import { Injectable, signal } from '@angular/core';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

import { SecureTokenStore } from './secure-token.store';
import { defaultApiUrl } from './connection-target';

function runsInTauri(): boolean {
  return '__TAURI_INTERNALS__' in window;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private client: SupabaseClient | null = null;
  private authSubscription: { unsubscribe(): void } | null = null;
  readonly userEmail = signal<string | null>(null);
  readonly configured = signal(false);
  readonly serverConfigured = signal(false);
  readonly connectionMessage = signal('Scanner-Server verbinden, um die Anmeldung automatisch einzurichten.');

  constructor(private readonly tokens: SecureTokenStore) {
    this.configureFromStorage();
  }

  configure(url: string, publishableKey: string): void {
    if (this.client && localStorage.getItem('deal-scanner-supabase-url') === url &&
        localStorage.getItem('deal-scanner-supabase-key') === publishableKey) return;
    localStorage.setItem('deal-scanner-supabase-url', url);
    localStorage.setItem('deal-scanner-supabase-key', publishableKey);
    this.configureFromStorage();
  }

  async initializeFromServer(): Promise<void> {
    if (runsInTauri()) {
      try {
        const { invoke } = await import('@tauri-apps/api/core');
        const addresses = await invoke<string[]>('server_connection');
        if (addresses.length) {
          localStorage.setItem('deal-scanner-server-addresses', JSON.stringify(addresses));
          localStorage.setItem('deal-scanner-api-url', addresses[0]);
        }
      } catch { /* Older desktop versions can still use the saved server address. */ }
    }
    let addresses: string[] = [];
    try {
      const stored: unknown = JSON.parse(localStorage.getItem('deal-scanner-server-addresses') ?? '[]');
      if (Array.isArray(stored)) addresses = stored.filter((value): value is string => typeof value === 'string').slice(0, 5);
    } catch { /* A saved single address remains usable. */ }
    if (!addresses.length) addresses = [localStorage.getItem('deal-scanner-api-url') ?? defaultApiUrl(window.location, runsInTauri())];
    let failure = '';
    for (const base of addresses) {
      try {
        const response = await fetch(`${base.replace(/\/$/, '')}/api/v1/client-config`, {
          signal: AbortSignal.timeout(3000), credentials: 'omit', cache: 'no-store',
        });
        if (!response.ok) {
          failure = 'Der Scanner-Server liefert keine Verbindungskonfiguration. Serveradresse und Serverversion prüfen.';
          continue;
        }
        const config: unknown = await response.json();
        if (!config || typeof config !== 'object') continue;
        const values = config as Record<string, unknown>;
        if (values['authMode'] === 'development') {
          this.configured.set(false);
          this.connectionMessage.set('Diese Adresse gehört zum lokalen Entwicklungsbetrieb. Für deine Kontoanmeldung bitte den zentralen Scanner-Server verbinden.');
          return;
        }
        if (values['authMode'] !== 'supabase' || typeof values['supabaseUrl'] !== 'string' ||
            typeof values['supabasePublishableKey'] !== 'string' || !values['supabasePublishableKey']) {
          failure = 'Auf diesem Server fehlt die zentrale Anmeldekonfiguration. Sie muss einmal auf dem Server eingerichtet werden.';
          continue;
        }
        const url = new URL(values['supabaseUrl']);
        if (url.protocol !== 'https:' && url.protocol !== 'http:') continue;
        this.configure(values['supabaseUrl'], values['supabasePublishableKey']);
        localStorage.setItem('deal-scanner-api-url', base.replace(/\/$/, ''));
        this.serverConfigured.set(true);
        this.connectionMessage.set(`Anmeldung automatisch vom Scanner-Server eingerichtet: ${base}`);
        return;
      } catch { /* Try the next configured network path without transmitting login credentials. */ }
    }
    this.connectionMessage.set(failure || 'Scanner-Server nicht erreichbar. Serveradresse und Netzwerkverbindung prüfen.');
  }

  async connectToServer(address: string): Promise<void> {
    const addresses = address.split(/[\n,;]+/).map((value) => value.trim()).filter(Boolean);
    if (!addresses.length || addresses.length > 5) throw new Error('Bitte eine bis fünf Serveradressen eingeben.');
    const origins = addresses.map((value) => {
      const url = new URL(value);
      const parts = url.hostname.split('.').map(Number);
      const privateIp = parts.length === 4 && parts.every((part) => Number.isInteger(part) && part >= 0 && part <= 255) &&
        (parts[0] === 10 || parts[0] === 127 || (parts[0] === 192 && parts[1] === 168) || (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31));
      const local = url.hostname === 'localhost' || privateIp;
      if ((url.protocol !== 'https:' && !(url.protocol === 'http:' && local)) ||
          url.username || url.password || url.search || url.hash || url.pathname !== '/') {
        throw new Error('Bitte HTTPS verwenden; HTTP ist nur für lokale Serveradressen erlaubt.');
      }
      return url.origin;
    });
    if (runsInTauri()) {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('save_server_connection', { addresses: [...new Set(origins)] });
    }
    localStorage.setItem('deal-scanner-server-addresses', JSON.stringify([...new Set(origins)]));
    localStorage.setItem('deal-scanner-api-url', origins[0]);
    this.authSubscription?.unsubscribe();
    void this.client?.auth.stopAutoRefresh();
    this.client = null;
    this.configured.set(false);
    this.serverConfigured.set(false);
    this.userEmail.set(null);
    localStorage.removeItem('deal-scanner-supabase-url');
    localStorage.removeItem('deal-scanner-supabase-key');
    await this.initializeFromServer();
    if (!this.serverConfigured()) throw new Error(this.connectionMessage());
  }

  async unlockDesktop(passphrase: string): Promise<boolean> {
    if (!runsInTauri()) return false;
    await this.tokens.unlockDesktop(passphrase);
    const stored = await this.tokens.getSessionTokens();
    if (!stored || !this.client) return false;
    const { data, error } = await this.client.auth.setSession({
      access_token: stored.accessToken,
      refresh_token: stored.refreshToken,
    });
    if (error) throw error;
    this.userEmail.set(data.user?.email ?? null);
    return Boolean(data.session);
  }

  async signIn(email: string, password: string, desktopPassphrase: string): Promise<void> {
    if (!this.client || !this.configured()) throw new Error(this.connectionMessage());
    if (runsInTauri()) await this.tokens.unlockDesktop(desktopPassphrase);
    const { data, error } = await this.client.auth.signInWithPassword({ email, password });
    if (error) throw error;
    if (!data.session) throw new Error('Supabase hat keine Sitzung zurückgegeben.');
    await this.tokens.setSessionTokens({
      accessToken: data.session.access_token,
      refreshToken: data.session.refresh_token,
    });
    this.userEmail.set(data.user.email ?? null);
    localStorage.setItem('deal-scanner-user-email', data.user.email ?? '');
  }

  async signOut(): Promise<void> {
    await this.client?.auth.signOut();
    await this.tokens.setSessionTokens(null).catch(() => undefined);
    this.userEmail.set(null);
  }

  private configureFromStorage(): void {
    const url = localStorage.getItem('deal-scanner-supabase-url');
    const key = localStorage.getItem('deal-scanner-supabase-key');
    if (!url || !key) return;
    this.authSubscription?.unsubscribe();
    void this.client?.auth.stopAutoRefresh();
    this.client = createClient(url, key, {
      auth: {
        persistSession: !runsInTauri(),
        autoRefreshToken: true,
        detectSessionInUrl: !runsInTauri(),
      },
    });
    this.configured.set(true);
    void this.client.auth.getSession().then(async ({ data }) => {
      if (!data.session) return;
      this.userEmail.set(data.session.user.email ?? null);
      await this.tokens.setSessionTokens({
        accessToken: data.session.access_token,
        refreshToken: data.session.refresh_token,
      });
    });
    const { data: listener } = this.client.auth.onAuthStateChange((_event, session) => {
      this.userEmail.set(session?.user.email ?? null);
      if (session) {
        void this.tokens
          .setSessionTokens({
            accessToken: session.access_token,
            refreshToken: session.refresh_token,
          })
          .catch(() => undefined);
      }
    });
    this.authSubscription = listener.subscription;
  }
}
