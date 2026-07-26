import { Routes } from '@angular/router';

import { CatalogPage } from './catalog.page';
import { ConflictsPage } from './conflicts.page';
import { DashboardPage } from './dashboard.page';
import { ListingDetailPage } from './listing-detail.page';
import { ListingsPage } from './listings.page';
import { ManualImportPage } from './manual-import.page';
import { PricesPage } from './prices.page';
import { QueuePage } from './queue.page';
import { SearchProfilesPage } from './search-profiles.page';
import { SystemPage } from './system.page';
import { WorkersPage } from './workers.page';
import { requireAuthentication } from './auth.guard';

const authenticatedRoutes: Routes = [
  { path: '', component: DashboardPage, title: 'Dashboard' },
  { path: 'search-profiles', component: SearchProfilesPage, title: 'Suchaufträge' },
  { path: 'listings', component: ListingsPage, title: 'Angebote', data: { title: 'Alle Angebote', view: 'all' } },
  { path: 'listings/:id', component: ListingDetailPage, title: 'Angebot' },
  { path: 'new-listings', component: ListingsPage, title: 'Neue Angebote', data: { title: 'Neue Angebote', view: 'new' } },
  { path: 'top-rated', component: ListingsPage, title: 'Beste Angebote', data: { title: 'Beste Angebote', view: 'top_rated' } },
  { path: 'favorites', component: ListingsPage, title: 'Favoriten', data: { title: 'Favoriten', view: 'favorites' } },
  { path: 'hidden', component: ListingsPage, title: 'Ausgeblendete Angebote', data: { title: 'Ausgeblendete Angebote', view: 'hidden' } },
  { path: 'queue', component: QueuePage, title: 'Analysewarteschlange' },
  { path: 'prices', component: PricesPage, title: 'Preisverläufe' },
  { path: 'catalog', component: CatalogPage, title: 'Produktkatalog' },
  { path: 'conflicts', component: ConflictsPage, title: 'Konfliktauflösung' },
  { path: 'workers', component: WorkersPage, title: 'Worker' },
  { path: 'imports', component: ManualImportPage, title: 'Manueller Import' },
  { path: 'system', component: SystemPage, title: 'Systemstatus' },
];

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./login.page').then((module) => module.LoginPage),
    title: 'Anmelden',
  },
  {
    path: 'settings',
    loadComponent: () => import('./settings.page').then((module) => module.SettingsPage),
    title: 'Einstellungen',
  },
  ...authenticatedRoutes.map((route) => ({
    ...route,
    canActivate: [requireAuthentication],
  })),
  { path: '**', redirectTo: '' },
];
