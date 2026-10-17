import { BreakpointObserver, Breakpoints } from '@angular/cdk/layout';
import { AsyncPipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatListModule } from '@angular/material/list';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { map } from 'rxjs';

import { NavIconComponent, type NavIconName } from './nav-icon.component';

@Component({
  selector: 'ds-root',
  standalone: true,
  imports: [
    AsyncPipe,
    MatButtonModule,
    MatListModule,
    MatSidenavModule,
    MatToolbarModule,
    NavIconComponent,
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
  ],
  template: `
    <mat-sidenav-container class="shell">
      <mat-sidenav #drawer [mode]="(isHandset$ | async) ? 'over' : 'side'" [opened]="!(isHandset$ | async)">
        <div class="brand"><span class="brand-mark">DS</span><strong>Deal Scanner</strong></div>
        <mat-nav-list>
          @if (native) {
            <a mat-list-item routerLink="/local-device" routerLinkActive="active"><ds-nav-icon matListItemIcon name="computer" /><span matListItemTitle>Dieses Gerät · KI</span></a>
          }
          @if (!native) {
          @for (item of navigation; track item.path) {
            <a mat-list-item [routerLink]="item.path" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: item.path === '/' }">
              <ds-nav-icon matListItemIcon [name]="item.icon" />
              <span matListItemTitle>{{ item.label }}</span>
            </a>
          }
          }
        </mat-nav-list>
      </mat-sidenav>
      <mat-sidenav-content>
        <mat-toolbar>
          @if (isHandset$ | async) {
            <button mat-icon-button (click)="drawer.toggle()" aria-label="Navigation öffnen"><ds-nav-icon name="menu" /></button>
          }
          <span class="spacer"></span>
          <span class="connection">Dein Deal-Workspace</span>
        </mat-toolbar>
        <main><router-outlet /></main>
      </mat-sidenav-content>
    </mat-sidenav-container>
  `,
  styles: `
    .shell { height: 100vh; }
    mat-sidenav { width: 272px; border-right: 1px solid var(--line); background: var(--surface); }
    mat-toolbar { position: sticky; top: 0; z-index: 4; background: color-mix(in srgb, var(--background) 88%, transparent); backdrop-filter: blur(16px); border-bottom: 1px solid var(--line); }
    main { padding: 36px; max-width: 1500px; margin: 0 auto; }
    mat-nav-list { padding: 8px 12px; }
    mat-nav-list a { margin-bottom: 3px; }
    [matListItemTitle] { font-size: 14px; letter-spacing: 0; }
    .brand { height: 74px; display: flex; align-items: center; gap: 12px; padding: 0 20px; letter-spacing: -.02em; }
    .brand-mark { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 11px; color: #ffffff; background: var(--accent); font-weight: 600; font-size: 14px; }
    .active { background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--accent); border-radius: 10px; }
    .active [matListItemTitle], .active ds-nav-icon { color: var(--accent); }
    .spacer { flex: 1; }
    .connection { font-size: 13px; color: var(--muted); display: flex; align-items: center; gap: 8px; }
    @media (max-width: 700px) { main { padding: 18px; } }
  `,
})
export class AppComponent {
  readonly native = '__TAURI_INTERNALS__' in window;
  private readonly breakpoints = inject(BreakpointObserver);
  readonly isHandset$ = this.breakpoints.observe(Breakpoints.Handset).pipe(map((result) => result.matches));
  readonly navigation: ReadonlyArray<{ path: string; label: string; icon: NavIconName }> = [
    { path: '/', label: 'Dashboard', icon: 'dashboard' },
    { path: '/search-profiles', label: 'Suchaufträge', icon: 'manage_search' },
    { path: '/new-listings', label: 'Neue Angebote', icon: 'new_releases' },
    { path: '/listings', label: 'Alle Angebote', icon: 'view_list' },
    { path: '/favorites', label: 'Favoriten', icon: 'favorite' },
    { path: '/queue', label: 'Analysewarteschlange', icon: 'memory' },
    { path: '/prices', label: 'Preisverläufe', icon: 'query_stats' },
    { path: '/catalog', label: 'Produktkatalog', icon: 'inventory_2' },
    { path: '/conflicts', label: 'Konflikte', icon: 'sync_problem' },
    { path: '/workers', label: 'Worker', icon: 'computer' },
    { path: '/imports', label: 'Importstatus', icon: 'sync' },
    { path: '/system', label: 'Systemstatus', icon: 'monitor_heart' },
    { path: '/settings', label: 'Einstellungen', icon: 'settings' },
    { path: '/login', label: 'Anmelden', icon: 'login' },
  ];
}
