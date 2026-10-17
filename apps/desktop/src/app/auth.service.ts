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
    const base = localStorage.getItem('deal-scanner-api-url') ??
      defaultApiUrl(window.location, runsInTauri());
    try {
      const response = await fetch(`${base.replace(/\/$/, '')}/api/v1/client-config`, {
        signal: AbortSignal.timeout(5000),
        credentials: 'omit',
        cache: 'no-store',
      });
      if (!response.ok) return;
      const config: unknown = await response.json();
      if (!config || typeof config !== 'object') return;
      const values = config as Record<string, unknown>;
      if (values['authMode'] !== 'supabase' || typeof values['supabaseUrl'] !== 'string' ||
          typeof values['supabasePublishableKey'] !== 'string' || !values['supabasePublishableKey']) return;
      const url = new URL(values['supabaseUrl']);
      if (url.protocol !== 'https:' && url.protocol !== 'http:') return;
      this.configure(values['supabaseUrl'], values['supabasePublishableKey']);
      this.serverConfigured.set(true);
    } catch {
      // Offline or older server: keep the existing manual configuration usable.
    }
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
    if (!this.client) throw new Error('Supabase ist noch nicht konfiguriert.');
    if (runsInTauri()) await this.tokens.unlockDesktop(desktopPassphrase);
    const { data, error } = await this.client.auth.signInWithPassword({ email, password });
    if (error) throw error;
    if (!data.session) throw new Error('Supabase hat keine Sitzung zurückgegeben.');
    await this.tokens.setSessionTokens({
      accessToken: data.session.access_token,
      refreshToken: data.session.refresh_token,
    });
    this.userEmail.set(data.user.email ?? null);
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
