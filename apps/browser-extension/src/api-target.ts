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
  const parts = parsed.hostname.split('.').map(Number);
  const privateIp = parts.length === 4 && parts.every((part) => Number.isInteger(part) && part >= 0 && part <= 255)
    && (parts[0] === 10 || parts[0] === 127 || (parts[0] === 192 && parts[1] === 168)
      || (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31));
  const local = parsed.hostname === 'localhost' || privateIp;
  if (parsed.protocol !== 'https:' && !(parsed.protocol === 'http:' && local)) {
    throw new Error('HTTPS ist Pflicht; HTTP ist nur für lokale IPv4-Adressen erlaubt.');
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
