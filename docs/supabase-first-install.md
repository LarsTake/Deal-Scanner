# Supabase: sichere Erstinstallation im SQL Editor

Die Anwendung nutzt **`deal_scanner`**, nicht `public`. Eine leere Tabellenliste
für `public` sagt deshalb nichts über eine frühere Deal-Scanner-Installation aus.

## Installation

1. Das gewünschte, wieder aktivierte Projekt im Supabase-Dashboard auswählen.
2. SQL Editor → neue Abfrage öffnen. Oben prüfen, dass wirklich das richtige
   Projekt gewählt ist. Das Skript enthält bewusst keine fest codierte Projekt-ID.
3. Die **gesamte** Datei [install.sql](../infrastructure/supabase/install.sql)
   hineinkopieren und als Administrator (`postgres`) ausführen. Keine einzelnen
   markierten Teile ausführen: Schutzprüfungen und Installation gehören zusammen.
4. Erwartetes Ergebnis: **27 Tabellennamen**, jeweils `rls_enabled = true`.
5. Bei einem Fehler die vollständige Fehlermeldung ohne Zugangsdaten weitergeben.
   Kein Schema löschen und nicht einzelne Schutzprüfungen entfernen.

Das Skript erstellt Tabellen, Funktionen, RLS-Regeln und zwei private Storage-Buckets
(`listing-images`, `mail-archive`). Neue Supabase-Auth-Benutzer bekommen über einen
Trigger ihren eigenen Workspace. Es werden keine Testdaten, Benutzer oder Passwörter
angelegt. Vorhandene Auth-Benutzer werden nicht nachträglich verändert; deren
Workspace-Zuordnung muss anschließend separat geprüft/eingerichtet werden.

## Schutz und Grenzen

- Die Installation läuft in einer Transaktion: Bei einem SQL-Fehler wird sie
  nicht teilweise übernommen. Eine Wiederholung ist **kein Update**, sondern
  bricht wegen des vorhandenen Schemas sicher ab.
- Ein vorhandenes Schema `deal_scanner`, der gleichnamige Auth-Trigger,
  die beiden Bucketnamen oder bereits vorhandene Storage-Policies führen zum Abbruch.
  Letztere müssen geprüft werden, da breite Regeln anderer Apps sonst auch neue
  private Buckets zugänglich machen könnten.
- Tabellen in `public` werden weder gelöscht noch ersetzt. Bestehende
  Buckets werden nicht umkonfiguriert. Die kanonischen Migrationen bleiben unverändert.
- Mindestversion PostgreSQL 15; Supabase Auth/Storage und die üblichen Rollen
  müssen bereits vorhanden sein. Das ist kein Installer für einen nackten PostgreSQL-Server.
- Das Skript veröffentlicht weder API noch Datenbank und richtet keine Ports,
  Secrets, Worker, Backups oder Windows-Dienste ein. Das folgt im Deployment-Schritt.
- Installation per SQL Editor schreibt keine Supabase-CLI-Migrationshistorie.
  Vor späteren CLI-Updates muss die Historie gezielt abgeglichen werden;
  nicht unbesehen die Initialmigration noch einmal anwenden.

## Entwickler: reproduzierbarer Build und Prüfung

```sh
uv run --no-sync python infrastructure/scripts/build_supabase_install.py
uv run --no-sync python infrastructure/scripts/build_supabase_install.py --check
uv run --no-sync pytest tests/test_supabase_install.py
```

Die generierte Datei enthält die Quell-Hashes der Migrationen. Der Builder entfernt
im Erstinstallations-Artefakt das Ersetzen des Auth-Triggers und das Bucket-Upsert;
beide Ressourcen werden nur neu angelegt, andernfalls schlägt die Transaktion fehl.

Lokal mit PostgreSQL 17 in einem isolierten Wegwerf-Container geprüft:
Erstinstallation, 27 Tabellen/RLS, Workspace-Erzeugung und Zugriffstrennung,
Abbruch bei Wiederholung sowie Schutz vorhandener Schemas, Buckets und Auth-Trigger.
Die Tests verwenden simulierte Supabase-Auth-/Storage-Tabellen, nicht das Liveprojekt.
