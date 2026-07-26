import { Injectable, signal } from '@angular/core';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

import { SecureTokenStore } from './secure-token.store';

function runsInTauri(): boolean {
  return '__TAURI_INTERNALS__' in window;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private client: SupabaseClient | null = null;
  readonly userEmail = signal<string | null>(null);
  readonly configured = signal(false);

  constructor(private readonly tokens: SecureTokenStore) {
    this.configureFromStorage();
  }

  configure(url: string, publishableKey: string): void {
    localStorage.setItem('deal-scanner-supabase-url', url);
    localStorage.setItem('deal-scanner-supabase-key', publishableKey);
    this.configureFromStorage();
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

  async signUp(email: string, password: string, desktopPassphrase: string): Promise<boolean> {
    if (!this.client) throw new Error('Supabase ist noch nicht konfiguriert.');
    if (runsInTauri()) await this.tokens.unlockDesktop(desktopPassphrase);
    const { data, error } = await this.client.auth.signUp({ email, password });
    if (error) throw error;
    if (!data.session) return false;
    await this.tokens.setSessionTokens({
      accessToken: data.session.access_token,
      refreshToken: data.session.refresh_token,
    });
    this.userEmail.set(data.user?.email ?? email);
    return true;
  }

  async requestPasswordReset(email: string): Promise<void> {
    if (!this.client) throw new Error('Supabase ist noch nicht konfiguriert.');
    const { error } = await this.client.auth.resetPasswordForEmail(email);
    if (error) throw error;
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
    this.client.auth.onAuthStateChange((_event, session) => {
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
  }
}
