import { Injectable } from '@angular/core';

interface DesktopVault {
  save(): Promise<void>;
  store: {
    get(key: string): Promise<Uint8Array | null>;
    insert(key: string, value: number[]): Promise<void>;
    remove(key: string): Promise<Uint8Array | null>;
  };
}

export interface StoredSessionTokens {
  accessToken: string;
  refreshToken: string;
}

function runsInTauri(): boolean {
  return '__TAURI_INTERNALS__' in window;
}

@Injectable({ providedIn: 'root' })
export class SecureTokenStore {
  private vault: DesktopVault | null = null;

  async unlockDesktop(passphrase: string): Promise<void> {
    if (!runsInTauri()) return;
    const [{ Stronghold }, { appDataDir }] = await Promise.all([
      import('@tauri-apps/plugin-stronghold'),
      import('@tauri-apps/api/path'),
    ]);
    const stronghold = await Stronghold.load(`${await appDataDir()}/deal-scanner-vault.hold`, passphrase);
    const client = await stronghold
      .loadClient('deal-scanner')
      .catch(() => stronghold.createClient('deal-scanner'));
    this.vault = { stronghold, store: client.getStore(), save: () => stronghold.save() } as unknown as DesktopVault;
  }

  async getAccessToken(): Promise<string | null> {
    if (!runsInTauri()) return sessionStorage.getItem('deal-scanner-access-token');
    return (await this.getSessionTokens())?.accessToken ?? null;
  }

  async getSessionTokens(): Promise<StoredSessionTokens | null> {
    if (!runsInTauri()) return null;
    if (!this.vault) return null;
    const bytes = await this.vault.store.get('supabase-session');
    if (!bytes) return null;
    return JSON.parse(new TextDecoder().decode(bytes)) as StoredSessionTokens;
  }

  async setSessionTokens(tokens: StoredSessionTokens | null): Promise<void> {
    if (!runsInTauri()) {
      if (tokens) sessionStorage.setItem('deal-scanner-access-token', tokens.accessToken);
      else sessionStorage.removeItem('deal-scanner-access-token');
      return;
    }
    if (!this.vault) throw new Error('Der sichere Desktop-Tresor ist noch gesperrt.');
    if (tokens) {
      await this.vault.store.insert('supabase-session', [
        ...new TextEncoder().encode(JSON.stringify(tokens)),
      ]);
    } else {
      await this.vault.store.remove('supabase-session');
    }
    await this.vault.save();
  }
}
