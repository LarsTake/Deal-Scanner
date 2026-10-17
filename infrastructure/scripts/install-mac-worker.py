"""Install a per-user, text-only launchd worker without changing the server .env."""

from __future__ import annotations

import argparse
import asyncio
import os
import plistlib
import subprocess
from pathlib import Path

from deal_scanner_service_auth.check import run as check_auth


def install() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--supabase-url", required=True)
    parser.add_argument("--publishable-key", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    worker = root / ".venv/bin/deal-scanner-worker"
    if not worker.is_file():
        raise SystemExit("Worker fehlt: zuerst uv sync --all-packages --frozen ausführen.")
    private = root / ".secrets"
    private.mkdir(mode=0o700, exist_ok=True)
    password_file = private / "mac-worker-password"
    if not password_file.exists():
        result = subprocess.run(
            [
                "/usr/bin/osascript",
                "-e",
                'text returned of (display dialog "Passwort für deine Deal-Scanner-Anmeldung '
                '(NICHT das Datenbankpasswort):" default answer "" with hidden answer '
                'with title "Deal Scanner – Mac-Worker" buttons {"Abbrechen", "Verbinden"} '
                'default button "Verbinden" cancel button "Abbrechen")',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode or not result.stdout.rstrip("\r\n"):
            raise SystemExit("Einrichtung abgebrochen; kein Hintergrunddienst installiert.")
        fd = os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(result.stdout.rstrip("\r\n"))
    password_file.chmod(0o600)
    runtime = root / ".data/mac-worker"
    runtime.mkdir(parents=True, mode=0o700, exist_ok=True)
    env = {
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        "DEAL_SCANNER_ENVIRONMENT": "production",
        "DEAL_SCANNER_API_URL": args.api_url,
        "DEAL_SCANNER_SERVICE_AUTH_MODE": "supabase",
        "DEAL_SCANNER_SERVICE_EMAIL": args.email,
        "DEAL_SCANNER_SERVICE_PASSWORD_FILE": str(password_file),
        "DEAL_SCANNER_SUPABASE_URL": args.supabase_url,
        "DEAL_SCANNER_SUPABASE_PUBLISHABLE_KEY": args.publishable_key,
        "DEAL_SCANNER_API_TOKEN": "",
        "DEAL_SCANNER_DEVELOPMENT_USER_ID": "",
        "DEAL_SCANNER_WORKER_MODE": "ai",
        "DEAL_SCANNER_WORKER_NAME": "Mac-Text-KI",
        "DEAL_SCANNER_OLLAMA_URL": "http://127.0.0.1:11434",
        "DEAL_SCANNER_OLLAMA_EXTRACTION_MODEL": args.model,
        "DEAL_SCANNER_OLLAMA_TEXT_MODEL": "",
        "DEAL_SCANNER_OLLAMA_REASONING_MODEL": "",
        "DEAL_SCANNER_OLLAMA_VISION_MODEL": "",
        "DEAL_SCANNER_OLLAMA_EMBEDDING_MODEL": "",
        "DEAL_SCANNER_TESSERACT_COMMAND": "disabled",
        "DEAL_SCANNER_HEALTH_FILE": str(runtime / "heartbeat"),
        "PYTHONUNBUFFERED": "1",
    }
    os.environ.update(env)
    asyncio.run(check_auth())
    agents = Path.home() / "Library/LaunchAgents"
    agents.mkdir(parents=True, exist_ok=True)
    label = "de.deal-scanner.text-worker"
    destination = agents / f"{label}.plist"
    # Never overwrite an unrelated existing agent.
    if destination.exists():
        raise SystemExit(f"Dienst existiert bereits: {destination}. Keine Änderungen vorgenommen.")
    config = {
        "Label": label,
        "ProgramArguments": [str(worker)],
        "WorkingDirectory": str(runtime),
        "EnvironmentVariables": env,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "Nice": 10,
        "StandardOutPath": str(runtime / "worker.log"),
        "StandardErrorPath": str(runtime / "worker.err.log"),
    }
    with destination.open("xb") as stream:
        plistlib.dump(config, stream)
    destination.chmod(0o600)
    for name in ("worker.log", "worker.err.log"):
        path = runtime / name
        path.touch(mode=0o600, exist_ok=True)
        path.chmod(0o600)
    subprocess.run(  # noqa: S603 -- fixed executable and locally constructed plist path, no shell
        ["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", str(destination)],
        check=True,
    )
    print("Mac-Text-Worker installiert und gestartet. Autostart bei Benutzeranmeldung aktiv.")
    print(f"Protokolle: {runtime}")


if __name__ == "__main__":
    install()
