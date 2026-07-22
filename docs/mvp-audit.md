# MVP-Abdeckungsmatrix

| Bereich | Implementierungsnachweis | Automatischer Nachweis |
|---|---|---|
| Web/Desktop | Angular-Seiten, Tauri-Shell, Offline-Outbox und native Benachrichtigung | Typecheck, Web- und native CI-Builds |
| API/Auth/RLS | FastAPI, Supabase-JWKS, Workspace-Claims, eingeschränkte DB-Rolle | API-Isolation und PostgreSQL-RLS-Tests |
| Imports | manuell, offizielle eBay-Browse-API, MV3-Pairing, versionierter IMAP-Parser | Provider-, Deduplizierungs- und Fixture-Tests |
| Historie | append-only Snapshots/Analysen/Audit, aktive Version nur als Referenz | Import- und Korrektur-Historientests |
| Extraktion | Regeln vor KI, Aliase und vier versionierte Kategorieprofile | Normalisierungs- und Profilvalidierungstests |
| KI/Worker | Ollama-Port, Schema-Prüfung, atomare Leases, Renew/Retry/Dead-Letter | Worker- und Schemafehler-Tests |
| Markt/Scoring | gewichtete Quellen, Zeitgewicht, MAD, getrennte Deal-/Risikoscores | Marktwert-, Qualitäts- und Risikotests |
| Betrieb/Sicherheit | Compose, Multi-Arch, CSP/CORS, SSRF/MIME-Limits, Rate-Limits, Secret-Scan | CI-, Security- und Image-Tests |
| Erweiterbarkeit | Provider-, Identity-, AI-, Notification- und ERP-Ports | OpenAPI-/Contract-Drift-Check |

Die credential-gesteuerten Live-Smokes für Supabase, eBay, IMAP, Ollama und ntfy sind in
`acceptance.md` bewusst separat ausgewiesen; sie ändern nicht den lokalen Funktionsumfang.
