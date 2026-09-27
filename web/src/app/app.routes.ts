import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', title: 'Wellspring', loadComponent: () => import('./pages/dashboard').then(m => m.DashboardPage) },
  { path: 'licences', title: 'Licences | Wellspring', loadComponent: () => import('./pages/licences').then(m => m.LicencesPage) },
  { path: 'map', title: 'Map | Wellspring', loadComponent: () => import('./pages/map').then(m => m.MapPage) },
  { path: 'ask', title: 'Ask | Wellspring', loadComponent: () => import('./pages/ask').then(m => m.AskPage) },
  { path: 'about', title: 'About | Wellspring', loadComponent: () => import('./pages/about').then(m => m.AboutPage) },
  { path: '**', redirectTo: '' },
];
