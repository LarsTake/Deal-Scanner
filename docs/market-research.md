# Automatische Recherche von Angebotspreisen

Der Scheduler recherchiert nach jedem erfolgreichen Importzyklus bis zu drei
Angebote. `DEAL_SCANNER_MARKET_RESEARCH_ENABLED=false` schaltet die Recherche aus.
Es werden nur aktivierte Quellen genutzt: eBay mit Production-Zugangsdaten und
Kleinanzeigen bei eingeschalteter Websuche. Keine generische Suchmaschine und
keine vom Sprachmodell erfundenen Preise werden als Marktdaten gespeichert.

Die erste Version unterstützt vollständige Icy-Dock-MB-Modellnummern und
RTX/GTX/RX-Modelle mit expliziter Speicherkapazität. Varianten und Zustände müssen
übereinstimmen. Zubehör, Suchanzeigen, Mehrfachmengen und Bundles werden konservativ
ausgeschlossen. Unklare Produkte und Komplett-PCs bleiben ohne automatische
Einzelpreisbewertung. Das ist keine vollständige Produktidentitätslösung.

Pro Ziel werden maximal 20 Ergebnisse je Quelle gelesen, ohne den Preiskorridor
des ursprünglichen Suchauftrags zu übernehmen. Pro Quelle gilt ein Zeitlimit
von 45 Sekunden. Erfolgreiche Recherchen (auch ohne Treffer) werden sechs Stunden
lang nicht wiederholt. Fehlgeschlagene Quellen werden im Scheduler-Protokoll
sichtbar; sie verhindern nicht Archivierung und Benachrichtigungsversand.
Das Auswahlfenster umfasst die 500 zuletzt gesehenen, sichtbaren Angebote.

Die API prüft Modell, Zustand, Währung, positive Preise und erlaubte HTTPS-Quellen
erneut. Das eigene Angebot und doppelte URLs zählen nicht als Vergleiche.
Ergebnisse werden idempotent als `active` gespeichert, mit Quell-URL, Titel und
serverseitigem Abrufzeitpunkt. Nach dem Speichern erfolgt die Neuberechnung.
Nach 14 Tagen gelten recherchierte Preise nicht mehr als aktuell. Ein zeitgleich
laufender Scheduler wird zusätzlich durch die bestehende PostgreSQL-Sperre
begrenzt; der API-Schreibzugriff sperrt das betroffene Angebot während des Imports.

Mindestens drei geeignete Vergleiche nach Ausreißerfilter sind erforderlich.
Aktive Angebote erhalten geringeres Gewicht als bestätigte Verkäufe. Unbekannte
Versandkosten werden als nicht eingerechnet ausgewiesen. Es handelt sich um eine
Schätzung aus verlangten Preisen, nicht um nachgewiesene Verkaufserlöse.
In den Angebotsdetails sind die verwendeten Quellen einzeln verlinkt.

Deployment: API, Scheduler und Weboberfläche aktualisieren. Keine neue SQL-Migration
notwendig; bestehende Preisbeobachtungen und Audit-Ereignisse werden verwendet.
Ein Desktop-App-Update allein aktiviert die serverseitige Recherche nicht.
