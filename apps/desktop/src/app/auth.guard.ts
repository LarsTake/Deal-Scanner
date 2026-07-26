import { inject, Injector } from '@angular/core';
import { type CanActivateFn, Router } from '@angular/router';

export const requireAuthentication: CanActivateFn = async (_route, state) => {
  const injector = inject(Injector);
  const router = inject(Router);
  const { AuthService } = await import('./auth.service');
  const auth = injector.get(AuthService);

  await auth.waitUntilInitialized();
  if (!auth.configured()) return router.createUrlTree(['/settings']);
  if (await auth.getAccessToken()) return true;

  return router.createUrlTree(['/login'], {
    queryParams: { returnUrl: state.url },
  });
};
