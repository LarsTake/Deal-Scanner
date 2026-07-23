import { Component, computed, input } from '@angular/core';

const ICON_PATHS = {
  dashboard: 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
  manage_search: 'M10 4a6 6 0 1 0 0 12 6 6 0 0 0 0-12 M14.5 14.5 20 20',
  new_releases: 'M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z',
  view_list: 'M8 6h12 M8 12h12 M8 18h12 M4 6h.01 M4 12h.01 M4 18h.01',
  favorite: 'M12 20S4 15.4 4 9.5A4.5 4.5 0 0 1 12 6.7 4.5 4.5 0 0 1 20 9.5C20 15.4 12 20 12 20z',
  memory: 'M8 8h8v8H8z M9 2v3 M15 2v3 M9 19v3 M15 19v3 M2 9h3 M2 15h3 M19 9h3 M19 15h3',
  query_stats: 'M4 18l6-6 4 4 6-8 M16 8h4v4',
  inventory_2: 'M4 7h16v13H4z M3 4h18v3H3z M9 11h6',
  sync_problem: 'M12 4a8 8 0 0 1 7.4 5 M20 4v5h-5 M12 20a8 8 0 0 1-7.4-5 M4 20v-5h5 M12 8v5 M12 17h.01',
  computer: 'M3 4h18v13H3z M8 21h8 M12 17v4',
  sync: 'M5 8a8 8 0 0 1 13-2l2 2 M20 4v4h-4 M19 16a8 8 0 0 1-13 2l-2-2 M4 20v-4h4',
  monitor_heart: 'M3 5h18v13H3z M7 12h3l2-4 2 7 2-3h2 M9 22h6',
  settings: 'M4 7h10 M18 7h2 M4 17h2 M10 17h10 M14 4v6 M6 14v6',
  login: 'M14 5h5v14h-5 M10 8l4 4-4 4 M14 12H3',
  menu: 'M4 6h16 M4 12h16 M4 18h16',
} as const;

export type NavIconName = keyof typeof ICON_PATHS;

@Component({
  selector: 'ds-nav-icon',
  standalone: true,
  template: `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path [attr.d]="path()" />
    </svg>
  `,
  styles: `
    :host { display: inline-grid; place-items: center; width: 24px; height: 24px; flex: 0 0 24px; }
    svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
  `,
})
export class NavIconComponent {
  readonly name = input.required<NavIconName>();
  readonly path = computed(() => ICON_PATHS[this.name()]);
}
