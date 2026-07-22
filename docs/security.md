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
- Erweiterungsimporte benötigen einen kurzlebigen Pairing-Token; nur dessen SHA-256-Hash wird gespeichert.
- E-Mails und Bilder liegen privat; Logs enthalten keine Tokens, vollständigen Mailtexte oder PII.
- Cloud-Modelle sind standardmäßig deaktiviert. Verkäuferkontakte und automatische Käufe sind kein Bestandteil.
