# Vorhandene Angebote mit cURL importieren

Die bestehende API akzeptiert vollständige Angebotsdaten per
`POST /api/v1/imports/browser`. Ein Link allein reicht hier nicht: Titel, Preis,
externe ID und vorhandene Beschreibung werden im JSON übergeben. Der Endpunkt
ruft die Angebotsseite nicht selbst ab. Für eBay gibt es zusätzlich den manuellen
Import über die offizielle API; dafür benötigt der Server eBay-Zugangsdaten.

## JSON-Datei

Die folgende Datei als `angebot.json` in UTF-8 speichern. Beispielwerte durch
die eigenen Angebotsdaten ersetzen:

```json
{
  "platform": "kleinanzeigen",
  "externalId": "1234567890",
  "url": "https://www.kleinanzeigen.de/s-anzeige/beispiel/1234567890-225-1234",
  "title": "Gaming-PC mit RTX 4070",
  "description": "Vollständige Artikelbeschreibung des Verkäufers.\nRyzen 7, 32 GB RAM, 1 TB SSD.\nAbholung und Funktionstest möglich.",
  "price": "650.00",
  "shippingCost": "0.00",
  "currency": "EUR",
  "location": "Berlin",
  "categoryProfile": "computer",
  "providerVersion": "curl-import-v1",
  "rawData": { "source": "existing-export" }
}
```

Optional kann `searchProfileId` mit der UUID eines eigenen Suchauftrags ergänzt
werden. Das erlaubt später den Filter **Suchaufträge → Treffer ansehen**.
Erlaubte Plattformen sind `ebay`, `kleinanzeigen`, `mydealz`, `vinted`, `manual`;
Kategorien sind `computer`, `simracing`, `fpv`, `general`.

## Windows PowerShell

Unter **Einstellungen → Dauerhafte Kontoverbindung** ein widerrufbares
Geräte-Token erzeugen. Es ist nur für Browser- und Bildimporte berechtigt.
Das Token als Umgebungsvariable `SCANNER_IMPORT_TOKEN` bereitstellen, nicht in
die JSON-Datei oder ins Repository schreiben. Dann im Ordner der Datei:

```powershell
$scannerUrl = 'https://scanner.example.com'
curl.exe --fail-with-body --request POST "$scannerUrl/api/v1/imports/browser" `
  --header "X-Extension-Pairing: $env:SCANNER_IMPORT_TOKEN" `
  --header 'Content-Type: application/json' `
  --header 'Idempotency-Key: import-1234567890-v1' `
  --data-binary '@angebot.json'
```

Alternativ ist `Authorization: Bearer <SUPABASE_ACCESS_TOKEN>` möglich.
In PowerShell ausdrücklich `curl.exe` verwenden, damit nicht der ältere Alias
für `Invoke-WebRequest` aufgerufen wird. Serveradresse durch die eigene ersetzen.

Erfolgreiche Importe antworten mit HTTP 201 und der Angebots-ID. Die Kombination
aus Workspace, Plattform und externer ID identifiziert das Angebot. Neue Inhalte
können einen neuen Snapshot und Analysejobs erzeugen; unveränderte Daten werden
dedupliziert. Bei einer Änderung auch einen neuen `Idempotency-Key` verwenden:
derselbe Schlüssel mit anderen Daten führt zu HTTP 409.

Für mehrere Angebote je JSON-Objekt einen Request senden. Dieser Endpunkt
erwartet kein Array. Bild-URLs allein in `rawData` laden keine Bilder herunter;
Bilder werden separat über `POST /api/v1/listings/{id}/images` importiert.

## Artikelbeschreibungen

`description` speichert bis zu 100.000 Zeichen Klartext, einschließlich
Zeilenumbrüchen. Der Text wird in der Angebotsdetailansicht angezeigt und für die
Analyse verwendet. Fehlt er im Import, kann die API ihn nicht aus dem Link
rekonstruieren.

Die Browser-Erweiterung übernimmt auf einer geöffneten Angebotsdetailseite die
sichtbare Beschreibung. Suchergebnislisten enthalten häufig nur einen Kurztext.
Für vollständige Beschreibungen daher die Angebotsdetailseiten importieren oder
einen vorhandenen Export mit vollständigem `description`-Feld verwenden.
