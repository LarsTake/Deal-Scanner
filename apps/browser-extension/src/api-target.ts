export interface ApiTarget {
  apiUrl: string;
  permissionPattern: string;
}

export function validateApiTarget(value: string): ApiTarget {
  const apiUrl = value.trim().replace(/\/$/, '');
  let parsed: URL;
  try {
    parsed = new URL(apiUrl);
  } catch {
    throw new Error('Die API-Adresse ist ungültig.');
  }
  const isLoopback = ['127.0.0.1', 'localhost'].includes(parsed.hostname);
  if (parsed.protocol !== 'https:' && !(parsed.protocol === 'http:' && isLoopback)) {
    throw new Error('HTTPS ist Pflicht; HTTP ist nur für Loopback erlaubt.');
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error('Die API-Adresse darf keine Zugangsdaten, Query oder Fragment enthalten.');
  }
  return {
    apiUrl,
    // Chrome match patterns deliberately omit ports and therefore cover the ephemeral loopback port.
    permissionPattern: `${parsed.protocol}//${parsed.hostname}/*`,
  };
}
