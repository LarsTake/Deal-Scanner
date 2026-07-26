# Sicherheitskonzept

- Browser und Desktop erhalten nur Supabase-Publishable-Konfiguration, niemals Service-Schlüssel.
- FastAPI validiert JWTs über die Supabase-JWKS, wechselt vor jeder Abfrage in die
  Nicht-BYPASSRLS-Rolle `authenticated`, setzt den Benutzerclaim über alle Handler-Commits
  hinweg, setzt den ORM-Suchpfad auf `deal_scanner` und entfernt Rolle, Suchpfad sowie Claim
  vor Rückgabe der Pool-Verbindung.
- Produktionsstart mit `AUTH_MODE=development` wird blockiert.
- RLS gilt für jede Workspace-Tabelle; das Schema `deal_scanner` wird nicht als Supabase
  Data-API-Schema veröffentlicht. Worker greifen ausschließlich über Lease-Endpunkte zu.
- Import-URLs werden gegen Provider-Allowlisten geprüft. Private, Loopback- und Link-Local-Ziele
  werden nicht durch den Server abgerufen.
- Erweiterungsimporte benötigen einen kurzlebigen Pairing-Token; nur dessen SHA-256-Hash wird
  gespeichert. Der optionale Tauri-Proxy bindet ausschließlich an `127.0.0.1`, hält ebenfalls nur
  den Hash im Arbeitsspeicher, akzeptiert genau zwei Import-Routen, folgt keinen Redirects und
  beendet sich nach fünf Minuten oder beim manuellen Widerruf. Das Benutzer-JWT wird nie an die
  Erweiterung ausgegeben.
- Der native CSV-Dateidialog akzeptiert nur CSV-Dateien bis 2 MB, liest sie als UTF-8 und gibt
  ausschließlich Dateiname und Inhalt an den Webview zurück; lokale Dateipfade bleiben verborgen.
- E-Mails und Bilder liegen privat; Logs enthalten keine Tokens, vollständigen Mailtexte oder PII.
- Der öffentliche eBay-Kontolösch-Webhook akzeptiert Nutzdaten erst nach ECDSA-Prüfung der
  `X-EBAY-SIGNATURE` mit dem über eBays Notification API geladenen Schlüssel. Die Löschung läuft
  außerhalb von Workspace-RLS nur in einer eng begrenzten Compliance-Transaktion; ungültige
  Signaturen erhalten HTTP 412 und der Wiederholschutz speichert keine eBay-Kontoidentifikatoren.
- Cloud-Modelle sind standardmäßig deaktiviert. Verkäuferkontakte und automatische Käufe sind kein Bestandteil.

## Nachverfolgte RustSec-Ausnahmen

- `RUSTSEC-2026-0194` und `RUSTSEC-2026-0195` betreffen `quick-xml 0.39` ausschließlich im
  Linux-Buildwerkzeug `wayland-scanner`. Es verarbeitet dabei die fest versionierten
  Wayland-Protokollquellen, keine Listing-, Datei- oder Netzwerkdaten. `rfd` wird aktualisiert,
  sobald dessen Wayland-Abhängigkeit `quick-xml >=0.41` zulässt.
- `RUSTSEC-2023-0071` betrifft `rsa 0.9`, das nur als nicht aktivierter MySQL-Zweig von SQLx im
  Lockfile enthalten ist. Der Desktop aktiviert ausschließlich SQLite; `cargo tree --target all
  -i rsa` weist keinen Laufzeit- oder Buildpfad nach. Die Ausnahme entfällt, sobald SQLx den
  Eintrag nicht mehr in den aufgelösten Lockfile-Graphen übernimmt.

Die CI ignoriert ausschließlich diese drei Advisory-IDs; neue RustSec-Befunde lassen den Build
weiterhin fehlschlagen.
