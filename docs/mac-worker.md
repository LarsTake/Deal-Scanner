# Lokale Text-KI auf macOS

Die Website startet keine lokalen Programme. Ein LaunchAgent verarbeitet Aufgaben
auch bei geschlossenem Browser und startet bei der Benutzeranmeldung. Während des
Ruhezustands oder bei ausgeschaltetem Mac findet keine lokale Analyse statt.

Voraussetzungen: bestehende Projektinstallation mit `.venv`, laufendes Ollama mit
einem geeigneten installierten Textmodell und erreichbare Scanner-API.

```sh
.venv/bin/python infrastructure/scripts/install-mac-worker.py \
  --api-url http://DEIN-SERVER:8088 \
  --supabase-url https://DEIN-PROJEKT.supabase.co \
  --publishable-key DEIN-PUBLISHABLE-KEY \
  --email DEINE-LOGIN-EMAIL \
  --model DEIN-INSTALLIERTES-TEXTMODELL
```

Das Passwort wird verdeckt über einen macOS-Dialog eingegeben. Es liegt danach in
`.secrets/mac-worker-password` mit Benutzerrechten `0600` (nicht verschlüsselt).
Nicht teilen. Der Installationsassistent prüft die Anmeldung vor dem Dienststart.
Der Worker benötigt weder das Datenbankpasswort noch einen Service-Role-Key.

Die separate Konfiguration verändert die Server-`.env` nicht. Bild-/Tesseract-,
Embedding- und zusätzliche Reasoning-Modellstufen sind deaktiviert. Der Worker
meldet ausschließlich die Textfähigkeit an. Das konfigurierte Modell extrahiert
Fakten; eine separate KI-Risikoprüfung ist in diesem schlanken Profil nicht aktiv.
Die regelbasierte Bewertung auf dem Server bleibt bestehen.

Protokolle: `.data/mac-worker/worker.log` und `worker.err.log`. Diese Dateien können
Angebotsinformationen enthalten. LaunchAgent:
`~/Library/LaunchAgents/de.deal-scanner.text-worker.plist`.

Pausieren (bis zum nächsten Laden des Dienstes/Anmelden):

```sh
launchctl bootout "gui/$(id -u)/de.deal-scanner.text-worker"
```

Wieder starten:

```sh
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/de.deal-scanner.text-worker.plist"
```

Ollama muss ebenfalls laufen. Seine Autostart-Einstellung ist von diesem
LaunchAgent unabhängig. Ein Bildanalyse-Schalter in der Website ist noch nicht
implementiert; dieses Profil ist bewusst ausschließlich für Text vorgesehen.
