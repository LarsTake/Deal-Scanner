import { Injectable, signal } from '@angular/core';
import { createClient, type Session, type SupabaseClient } from '@supabase/supabase-js';

import { SecureTokenStore } from './secure-token.store';

const LOCAL_PASSWORD_RECOVERY_URL = 'http://127.0.0.1:4200/login';

function runsInTauri(): boolean {
  return '__TAURI_INTERNALS__' in window;
}

export function resolvePasswordRecoveryRedirect(
  origin: string = window.location.origin,
  isTauri: boolean = runsInTauri(),
): string {
  if (!isTauri) {
    try {
      const url = new URL(origin);
      if (
        (url.protocol === 'http:' || url.protocol === 'https:') &&
        url.hostname !== 'tauri.localhost'
      ) {
        return new URL('/login', url.origin).toString();
      }
    } catch {
      // Fall through to the local browser callback.
    }
  }
  return LOCAL_PASSWORD_RECOVERY_URL;
}

export function readAuthRedirectError(href: string = window.location.href): string | null {
  try {
    const url = new URL(href);
    const fragment = new URLSearchParams(url.hash.replace(/^#/, ''));
    return fragment.get('error_description') ?? url.searchParams.get('error_description');
  } catch {
    return null;
  }
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private client: SupabaseClient | null = null;
  readonly userEmail = signal<string | null>(null);
  readonly configured = signal(false);
  readonly passwordRecovery = signal(false);
  readonly redirectError = signal<string | null>(readAuthRedirectError());

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
    await this.storeSession(data.session);
  }

  async signUp(email: string, password: string, desktopPassphrase: string): Promise<boolean> {
    if (!this.client) throw new Error('Supabase ist noch nicht konfiguriert.');
    if (runsInTauri()) await this.tokens.unlockDesktop(desktopPassphrase);
    const { data, error } = await this.client.auth.signUp({ email, password });
    if (error) throw error;
    if (!data.session) return false;
    await this.storeSession(data.session);
    return true;
  }

  async requestPasswordReset(email: string): Promise<void> {
    if (!this.client) throw new Error('Supabase ist noch nicht konfiguriert.');
    this.redirectError.set(null);
    const { error } = await this.client.auth.resetPasswordForEmail(email, {
      redirectTo: resolvePasswordRecoveryRedirect(),
    });
    if (error) throw error;
  }

  async updatePassword(password: string): Promise<void> {
    if (!this.client) throw new Error('Supabase ist noch nicht konfiguriert.');
    if (!this.passwordRecovery()) throw new Error('Der Passwort-Link ist nicht mehr gültig.');
    const { error } = await this.client.auth.updateUser({ password });
    if (error) throw error;
    this.passwordRecovery.set(false);
    await this.signOut();
  }

  async signOut(): Promise<void> {
    await this.client?.auth.signOut();
    await this.tokens.setSessionTokens(null).catch(() => undefined);
    this.userEmail.set(null);
    this.passwordRecovery.set(false);
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
    this.client.auth.onAuthStateChange((event, session) => {
      if (event === 'PASSWORD_RECOVERY') {
        this.passwordRecovery.set(true);
        this.redirectError.set(null);
      }
      this.userEmail.set(session?.user.email ?? null);
      if (session) void this.storeSession(session).catch(() => undefined);
    });
    void this.initializeSession();
  }

  private async initializeSession(): Promise<void> {
    if (!this.client) return;
    const currentUrl = new URL(window.location.href);
    const tokenHash = currentUrl.searchParams.get('token_hash');
    const type = currentUrl.searchParams.get('type');
    if (tokenHash && type === 'recovery') {
      const { data, error } = await this.client.auth.verifyOtp({
        token_hash: tokenHash,
        type: 'recovery',
      });
      if (error) {
        this.redirectError.set(error.message);
        return;
      }
      this.passwordRecovery.set(Boolean(data.session));
      this.redirectError.set(null);
      this.removeRecoveryParameters(currentUrl);
      if (data.session) await this.storeSession(data.session);
      return;
    }

    const { data } = await this.client.auth.getSession();
    if (data.session) await this.storeSession(data.session);
  }

  private async storeSession(session: Session): Promise<void> {
    this.userEmail.set(session.user.email ?? null);
    await this.tokens.setSessionTokens({
      accessToken: session.access_token,
      refreshToken: session.refresh_token,
    });
  }

  private removeRecoveryParameters(url: URL): void {
    url.searchParams.delete('token_hash');
    url.searchParams.delete('type');
    window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
  }
}
