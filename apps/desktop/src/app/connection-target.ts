export function defaultApiUrl(location: Pick<Location, 'protocol' | 'hostname' | 'port' | 'origin'>, native: boolean): string {
  const localDevelopment = ['localhost', '127.0.0.1'].includes(location.hostname) && location.port === '4200';
  if (native || localDevelopment || !['http:', 'https:'].includes(location.protocol)) return 'http://127.0.0.1:8000';
  return location.origin;
}
