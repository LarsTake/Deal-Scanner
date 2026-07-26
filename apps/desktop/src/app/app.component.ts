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
          @for (item of navigation; track item.path) {
            <a mat-list-item [routerLink]="item.path" routerLinkActive="active" [routerLinkActiveOptions]="{ exact: item.path === '/' }">
              <ds-nav-icon matListItemIcon [name]="item.icon" />
              <span matListItemTitle>{{ item.label }}</span>
            </a>
          }
        </mat-nav-list>
      </mat-sidenav>
      <mat-sidenav-content>
        <mat-toolbar>
          @if (isHandset$ | async) {
            <button mat-icon-button (click)="drawer.toggle()" aria-label="Navigation öffnen"><ds-nav-icon name="menu" /></button>
          }
          <span class="spacer"></span>
          <span class="connection"><i></i> Lokaler Modus</span>
        </mat-toolbar>
        <main><router-outlet /></main>
      </mat-sidenav-content>
    </mat-sidenav-container>
  `,
  styles: `
    .shell { height: 100vh; }
    mat-sidenav { width: 255px; border-right: 1px solid var(--line); background: var(--surface); }
    mat-toolbar { position: sticky; top: 0; z-index: 4; background: color-mix(in srgb, var(--background) 88%, transparent); backdrop-filter: blur(16px); border-bottom: 1px solid var(--line); }
    main { padding: 28px; max-width: 1500px; margin: 0 auto; }
    .brand { height: 74px; display: flex; align-items: center; gap: 12px; padding: 0 20px; letter-spacing: -.02em; }
    .brand-mark { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 11px; color: #06120f; background: var(--accent); font-weight: 900; }
    .active { background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--accent); border-radius: 10px; }
    .spacer { flex: 1; }
    .connection { font-size: 13px; color: var(--muted); display: flex; align-items: center; gap: 8px; }
    .connection i { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 12px var(--accent); }
    @media (max-width: 700px) { main { padding: 18px; } }
  `,
})
export class AppComponent {
  private readonly breakpoints = inject(BreakpointObserver);
  readonly isHandset$ = this.breakpoints.observe(Breakpoints.Handset).pipe(map((result) => result.matches));
  readonly navigation: ReadonlyArray<{ path: string; label: string; icon: NavIconName }> = [
    { path: '/', label: 'Dashboard', icon: 'dashboard' },
    { path: '/search-profiles', label: 'Suchaufträge', icon: 'manage_search' },
    { path: '/new-listings', label: 'Neue Angebote', icon: 'new_releases' },
    { path: '/top-rated', label: 'Beste Angebote', icon: 'star' },
    { path: '/listings', label: 'Alle Angebote', icon: 'view_list' },
    { path: '/favorites', label: 'Favoriten', icon: 'favorite' },
    { path: '/hidden', label: 'Ausgeblendet', icon: 'sync_problem' },
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
