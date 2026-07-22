import { Injectable } from '@angular/core';

export interface SelectedTextFile {
  name: string;
  content: string;
}

function runsInTauri(): boolean {
  return '__TAURI_INTERNALS__' in window;
}

@Injectable({ providedIn: 'root' })
export class FileAccessService {
  async selectCsv(): Promise<SelectedTextFile | null> {
    if (runsInTauri()) {
      const { invoke } = await import('@tauri-apps/api/core');
      return invoke<SelectedTextFile | null>('select_csv_file');
    }
    return this.selectBrowserFile();
  }

  private selectBrowserFile(): Promise<SelectedTextFile | null> {
    return new Promise((resolve, reject) => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.csv,text/csv';
      input.hidden = true;
      input.addEventListener('cancel', () => {
        input.remove();
        resolve(null);
      }, { once: true });
      input.addEventListener('change', () => void (async () => {
        const file = input.files?.[0];
        input.remove();
        if (!file) { resolve(null); return; }
        if (file.size > 2_000_000) { reject(new Error('Die CSV-Datei überschreitet das Limit von 2 MB.')); return; }
        try {
          resolve({ name: file.name, content: await file.text() });
        } catch (error) {
          reject(error);
        }
      })());
      document.body.append(input);
      input.click();
    });
  }
}
