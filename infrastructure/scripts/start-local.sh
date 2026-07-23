#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
environment_file="$repository_root/.env"
runtime_directory="$repository_root/.data/runtime"
timestamp="$(date '+%Y%m%d-%H%M%S')"
install_dependencies=false
open_browser=true

usage() {
  echo "Usage: $0 [--install] [--no-browser]"
}

for argument in "$@"; do
  case "$argument" in
    --install) install_dependencies=true ;;
    --no-browser) open_browser=false ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unbekannte Option: $argument" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! -f "$environment_file" ]]; then
  echo "Die Datei .env fehlt. Erstelle sie mit: cp .env.example .env" >&2
  exit 1
fi

command -v uv >/dev/null || { echo "uv fehlt. Installation: brew install uv" >&2; exit 1; }
command -v corepack >/dev/null || { echo "Corepack fehlt. Installiere Node.js 24." >&2; exit 1; }

mkdir -p "$runtime_directory"
cd "$repository_root"

pnpm_command=(corepack pnpm)

if $install_dependencies; then
  uv --system-certs sync --all-packages --frozen
  "${pnpm_command[@]}" install --frozen-lockfile
fi

if [[ ! -f packages/typescript/contracts/dist/index.js || ! -f packages/typescript/api-client/dist/index.js ]]; then
  "${pnpm_command[@]}" --filter @deal-scanner/contracts build
  "${pnpm_command[@]}" --filter @deal-scanner/api-client build
fi

environment_value() {
  local name="$1"
  sed -n "s/^${name}=//p" "$environment_file" | tail -n 1
}

port_is_open() {
  nc -z 127.0.0.1 "$1" >/dev/null 2>&1
}

process_is_running() {
  pgrep -f "$1" >/dev/null 2>&1
}

start_logged_process() {
  local name="$1"
  shift
  nohup "$@" \
    >"$runtime_directory/$name-$timestamp.out.log" \
    2>"$runtime_directory/$name-$timestamp.err.log" \
    </dev/null &
  echo "$!" >"$runtime_directory/$name.pid"
  started+=("$name")
}

started=()
ollama_model="$(environment_value DEAL_SCANNER_OLLAMA_TEXT_MODEL)"
ollama_url="$(environment_value DEAL_SCANNER_OLLAMA_URL)"
if [[ -n "$ollama_model" && "$ollama_url" =~ ^http://(127\.0\.0\.1|localhost):([0-9]+) ]]; then
  ollama_port="${BASH_REMATCH[2]}"
  if ! port_is_open "$ollama_port" && command -v ollama >/dev/null; then
    start_logged_process ollama ollama serve
  fi
fi

if ! port_is_open 8000; then
  start_logged_process api uv --system-certs run --package deal-scanner-api \
    uvicorn deal_scanner_api.main:app --host 127.0.0.1 --port 8000
fi
if ! process_is_running '[d]eal-scanner-worker'; then
  start_logged_process worker uv --system-certs run --package deal-scanner-worker deal-scanner-worker
fi
if ! process_is_running '[d]eal-scanner-scheduler'; then
  start_logged_process scheduler uv --system-certs run --package deal-scanner-scheduler deal-scanner-scheduler
fi
if ! port_is_open 4200; then
  start_logged_process ui "${pnpm_command[@]}" --filter @deal-scanner/desktop start
fi

api_ready=false
ui_ready=false
for _ in $(seq 1 60); do
  curl --fail --silent --max-time 1 http://127.0.0.1:8000/api/v1/health/ready >/dev/null && api_ready=true || true
  curl --fail --silent --max-time 1 http://127.0.0.1:4200/ >/dev/null && ui_ready=true || true
  if $api_ready && $ui_ready; then
    break
  fi
  sleep 0.5
done

if ! $api_ready || ! $ui_ready; then
  echo "Lokaler Start unvollständig. API bereit: $api_ready; Oberfläche bereit: $ui_ready." >&2
  echo "Logs: $runtime_directory" >&2
  exit 1
fi

echo "Deal Scanner läuft: http://127.0.0.1:4200/"
echo "API-Dokumentation: http://127.0.0.1:8000/api/docs"
echo "Logs: $runtime_directory"
if ((${#started[@]})); then
  echo "Neu gestartete Prozesse: ${started[*]}"
else
  echo "Alle Prozesse liefen bereits."
fi

if $open_browser; then
  open http://127.0.0.1:4200/
fi
