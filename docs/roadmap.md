# Ausbau-Roadmap

Diese Punkte sind bewusst von der MVP-Abdeckungsmatrix getrennt: Sie beschreiben
geplante Erweiterungen und sind noch nicht als umgesetzt zu verstehen.

## 1. Öffentlicher Betrieb hinter Cloudflare

Die FastAPI-Anwendung bleibt die einzige fachliche API. Cloudflare erhält davor nur
die Aufgaben eines Edge-Frontends: eigene Domain, TLS, DDoS-/WAF-Schutz sowie
Rate-Limits für öffentliche Routen. Die Authentifizierung, RLS-Prüfung,
Geschäftslogik und Geheimnisse bleiben bei FastAPI und Supabase.

Ein Cloudflare Worker wird nicht als allgemeiner Proxy zwischen Desktop-App und
FastAPI eingesetzt. Das würde die Sicherheits- und Validierungslogik duplizieren.
Ein schmaler Worker ist erst dann sinnvoll, wenn eine konkrete Edge-Aufgabe besteht,
etwa eine signierte Callback-Route oder ein Cache für wirklich öffentliche,
nicht-personenbezogene Daten.

Umsetzungsschritte:

1. API auf einer geeigneten Server-Laufzeit bereitstellen und eine eigene Domain
   hinter Cloudflare schalten.
2. Öffentliche Eingänge mit WAF- und Rate-Limit-Regeln absichern; Admin- und
   Worker-Routen nicht öffentlich freigeben.
3. CORS, OAuth-Redirect-URLs, Observability und Fehlergrenzen mit der echten Domain
   testen.
4. Erst bei einem klaren Edge-Anwendungsfall Wrangler installieren und einen eng
   begrenzten Worker mit ausschließlich serverseitigen Secrets bereitstellen.

## 2. Komponentenbezogene Marktpreis-Referenzen

Ziel ist eine nachvollziehbare Preisansicht für einzelne Komponenten wie RAM,
SSDs, Grafikkarten oder CPUs. Sie ergänzt die vorhandene Bewertung ganzer Angebote:
Jede neue Schätzung soll sichtbar auf aktuellen Vergleichsdaten beruhen und nicht
unbemerkt auf veralteten oder widersprüchlichen Preisen.

### Daten und Herkunft

- Komponenten erhalten eine kanonische Identität: Hersteller, Modell/Serie,
  Kapazität, Geschwindigkeit bzw. Schnittstelle, Menge, Zustand und gegebenenfalls
  Bundle-/Lot-Größe.
- Jede Referenz bewahrt die Herkunft: Plattform, Angebots-ID und URL, beobachteter
  Zeitpunkt, Währung, Artikelpreis, Versand, Zustand, Suchanfrage,
  Match-Konfidenz und einen Verweis auf den Rohsnapshot.
- Aktive Angebote und bestätigte Verkäufe werden strikt getrennt gespeichert und
  angezeigt. Aktive Inserate sind Angebotspreise; sie sind kein Beleg dafür, dass
  zu diesem Preis verkauft wurde.
- Ein Preis eines vollständigen PCs wird nicht automatisch auf dessen Einzelteile
  verteilt. Nur eindeutig einzeln bepreiste Komponenten oder explizite Bundles
  werden als Komponentenreferenz genutzt.

### Quellenstrategie

Nach Freigabe der eBay-Zugangsdaten können aktive eBay-Angebote automatisiert als
frische Indikatoren abgefragt werden. Für allgemein verfügbare, bereits verkaufte
eBay-Angebote wird vor der Umsetzung eine zulässige Datenquelle benötigt: Die
eBay-Browse-API liefert aktuelle kaufbare Angebote, aber keine allgemeine
Markt-Verkaufshistorie. Verkaufsdaten aus einem eBay-Verkäuferkonto dürfen nur für
die eigenen Verkäufe dieses Kontos als Quelle genutzt werden.

Bis eine geeignete, lizenzierte Quelle entschieden ist, bleiben bestätigte
Referenzen aus dem vorhandenen CSV-Import oder manuell belegte Verkäufe möglich.
Kein Scraping von eBay-Seiten und keine als „verkauft“ ausgegebenen Schätzwerte.

### Bewertungslogik und Oberfläche

- Bestätigte Verkäufe erhalten mehr Gewicht als aktive Inserate. Beide Gruppen
  unterliegen Zeitgewichtung, Spezifikations-/Zustandsabgleich und Ausreißerprüfung.
- Die Ansicht zeigt Median bzw. Preisspanne, Zahl und Art der Referenzen, letzte
  Beobachtung, Datenalter und eine verständliche Qualitätsstufe.
- Bei stark schwankenden Komponenten (insbesondere RAM und SSDs) führt eine neue,
  hochwertige Beobachtung oder ein überschrittenes Frischeintervall zu einer
  Neubewertung. Kleine Einzelabweichungen ändern den Referenzpreis nicht sofort.
- Unklare Treffer, zu kleine Stichproben und zu alte Daten senken die Qualität,
  statt einen präzisen Marktwert vorzutäuschen.

### Umsetzungspakete

1. Datenmodell und Migration für Komponentenidentitäten, Referenzen, Match- und
   Provenance-Daten ergänzen.
2. Extraktionsregeln um Komponenten aus Produktanalysen erweitern und eine
   Prüfmöglichkeit für falsche Zuordnungen vorsehen.
3. eBay-Suche für aktive Referenzen implementieren, inklusive Deduplizierung,
   Rate-Limits, Caching und nachvollziehbarer Suchparameter.
4. Nach Entscheidung über die Verkaufsdatenquelle einen separaten Adapter für
   bestätigte Verkäufe bauen; Lizenz, Zugriffsumfang und Aktualisierungsintervall
   sind dabei Teil der Abnahme.
5. Marktwert-Engine, API und UI um Komponentenhistorie, Datenqualität und
   Quellenansicht erweitern; mit Fixtures für Ausreißer, Bundles, doppelte Treffer
   und volatile Preisreihen testen.

## Offene Produktentscheidung

Vor Paket 4 ist festzulegen, welche zulässige Quelle marktweite Verkaufspreise
liefert. Die eBay-Browse-Integration allein genügt dafür nicht. Diese Entscheidung
bestimmt Kosten, Lizenzbedingungen, Datenabdeckung und die Aussagekraft der
Komponentenpreise.
