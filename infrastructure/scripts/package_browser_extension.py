"""Package only the built extension, without local configuration or credentials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def package_extension(source: Path, output: Path) -> None:
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    required = {"manifest.json", "background.js", "content.js", "popup.html", "popup.js"}
    if manifest.get("manifest_version") != 3 or not all((source / name).is_file() for name in required):
        raise ValueError("Build the browser extension first: pnpm --filter @deal-scanner/browser-extension build")
    if sum(path.stat().st_size for path in source.rglob("*") if path.is_file()) > 20_000_000:
        raise ValueError("Extension build exceeds 20 MB")
    files = sorted(path for path in source.rglob("*") if path.is_file())
    for path in files:
        if path.is_symlink() or path.suffix not in {".json", ".js", ".html", ".css", ".png", ".svg"}:
            raise ValueError(f"Unexpected file in extension build: {path.name}")
        if path.suffix == ".json" and path.name != "manifest.json":
            raise ValueError("Only the extension manifest may be packaged as JSON")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(source).as_posix())
        archive.writestr(
            "INSTALLATION.txt",
            "Deal Scanner - Chrome\n\n"
            "1. ZIP in einen dauerhaften Ordner entpacken.\n"
            "2. chrome://extensions oeffnen und Entwicklermodus aktivieren.\n"
            "3. 'Entpackte Erweiterung laden' und diesen Ordner auswaehlen.\n"
            "4. Im Scanner-Dashboard im Browser anmelden.\n"
            "5. Erweiterung oeffnen: 'Mit geoeffnetem Scanner verbinden'.\n"
            "API und widerrufbares Geraete-Token werden automatisch uebernommen.\n"
            "6. Kleinanzeigen-Ergebnisseite oeffnen; Durchlauf im Popup starten.\n"
            "Seiten-/Angebotslimit und Pause einstellen. Stoppen ist jederzeit moeglich.\n"
            "Kein Autostart; keine Umgehung von Sicherheitsabfragen.\n",
        )


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "apps/browser-extension/dist")
    parser.add_argument("--output", type=Path, default=root / "artifacts/deal-scanner-chrome.zip")
    args = parser.parse_args()
    package_extension(args.source, args.output)
    print(f"Extension package: {args.output}")
