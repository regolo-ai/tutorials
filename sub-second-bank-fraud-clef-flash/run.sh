#!/usr/bin/env bash
# Check, start and stop the fraudclef console.
#
#   ./run.sh check      verify prerequisites, Regolo, policies, data and tests
#   ./run.sh start      check, then start the console on http://127.0.0.1:8080
#   ./run.sh stop       stop the console
#   ./run.sh restart    stop, then start
#   ./run.sh status     show whether the console is running
#
# Options: --skip-tests  --no-open  --port N  --fake (offline, no Regolo calls)

set -euo pipefail
cd "$(dirname "$0")"

PORT=8080
HOST=127.0.0.1          # localhost only: the console has no authentication
SKIP_TESTS=0
OPEN_BROWSER=1
BACKEND=regolo
PID_FILE=logs/ui.pid
LOG_FILE=logs/ui.log
REGOLO_BASE_URL_DEFAULT=https://api.regolo.ai

CMD="${1:-start}"
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-tests) SKIP_TESTS=1 ;;
    --no-open) OPEN_BROWSER=0 ;;
    --port) PORT="$2"; shift ;;
    --fake) BACKEND=fake ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [[ -t 1 ]]; then G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; B=$'\e[1m'; N=$'\e[0m'; else G=; Y=; R=; B=; N=; fi
ok()   { printf '  %s✓%s %s\n' "$G" "$N" "$1"; }
warn() { printf '  %s!%s %s\n' "$Y" "$N" "$1"; }
fail() { printf '  %s✗%s %s\n' "$R" "$N" "$1"; FAILED=1; }
step() { printf '\n%s%s%s\n' "$B" "$1" "$N"; }

# Read one KEY=value from .env without executing the file.
env_value() { [[ -f .env ]] && grep -E "^$1=" .env | tail -1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//' || true; }

running_pid() {
  [[ -f "$PID_FILE" ]] || return 1
  local pid; pid=$(cat "$PID_FILE")
  kill -0 "$pid" 2>/dev/null && echo "$pid" && return 0
  rm -f "$PID_FILE"; return 1
}

check() {
  FAILED=0
  step "Tools"
  if command -v uv >/dev/null; then ok "uv $(uv --version | awk '{print $2}')"; else fail "uv not found: install it with 'curl -LsSf https://astral.sh/uv/install.sh | sh'"; return 1; fi
  command -v curl >/dev/null && ok "curl" || fail "curl not found"

  step "Configuration"
  if [[ ! -f .env ]]; then
    # First run: create .env from the template with a random pseudonymisation secret.
    sed "s/^FRAUDCLEF_HMAC_KEY=.*/FRAUDCLEF_HMAC_KEY=$(openssl rand -hex 32)/" .env.example >.env
    chmod 600 .env
    ok ".env created from .env.example"
  else
    ok ".env present"
  fi
  local key hmac; key=$(env_value REGOLO_API_KEY); hmac=$(env_value FRAUDCLEF_HMAC_KEY)
  if [[ -z "$key" ]]; then warn "REGOLO_API_KEY not set: paste it in the console sidebar after start"; else ok "REGOLO_API_KEY set"; fi
  if [[ -z "$hmac" || "$hmac" == change-me ]]; then warn "FRAUDCLEF_HMAC_KEY not set: pseudonyms use an insecure development key"; else ok "FRAUDCLEF_HMAC_KEY set"; fi

  step "Dependencies"
  if uv sync -q 2>logs_sync.tmp; then ok "Python environment in sync"; else fail "uv sync failed: $(tail -3 logs_sync.tmp)"; fi
  rm -f logs_sync.tmp

  step "Policies"
  local out
  if out=$(uv run -q python - <<'PY' 2>&1
from pathlib import Path
from fraudclef.policy import load_policy
for p in sorted(Path("policies").glob("*.yaml")):
    print(load_policy(p).ref)
PY
  ); then while read -r line; do ok "$line"; done <<<"$out"; else fail "invalid policy: $(echo "$out" | tail -2)"; fi

  if [[ "$BACKEND" == regolo ]]; then
    step "Regolo"
    local base models code
    base=$(env_value REGOLO_BASE_URL); base=${base:-$REGOLO_BASE_URL_DEFAULT}
    if models=$(curl -fsS -m 8 "$base/models" 2>/dev/null); then
      ok "$base reachable"
      if grep -q '"clef-flash"' <<<"$models"; then ok "clef-flash listed"; else fail "clef-flash not in the Regolo model list"; fi
    else
      fail "$base unreachable (network or proxy?)"
    fi
    if [[ -n "$(env_value REGOLO_API_KEY)" ]]; then
      # Header from stdin, so the key never shows up in the process list.
      code=$(printf 'Authorization: Bearer %s\n' "$(env_value REGOLO_API_KEY)" | curl -s -o /dev/null -w '%{http_code}' -m 8 -H @- "$base/key/info" || echo 000)
      if [[ "$code" == 200 ]]; then ok "API key accepted"; else warn "API key rejected by Regolo (HTTP $code): replace it in the console sidebar"; fi
    fi
  fi

  step "Data"
  if [[ -z "$(ls data/scenarios/*.json 2>/dev/null)" || ! -f data/random_dataset.json ]]; then
    uv run -q fraudclef generate --random 2000 >/dev/null && ok "generated 27 European scenarios and 2,000 portfolio requests"
  else
    ok "$(ls data/scenarios/*.json | wc -l | tr -d ' ') scenarios and a random dataset present"
  fi

  if [[ $SKIP_TESTS == 0 ]]; then
    step "Offline tests"
    if out=$(uv run -q python -m pytest -q 2>&1); then ok "$(tail -1 <<<"$out")"; else fail "tests failed:"; echo "$out" | tail -15; fi
  fi

  step "Port"
  if pid=$(running_pid); then
    warn "console already running (pid $pid) on port $PORT"
  elif lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    fail "port $PORT is in use by another process: use --port N"
  else
    ok "port $PORT free"
  fi

  echo
  if [[ $FAILED == 0 ]]; then printf '%sAll checks passed.%s\n' "$G" "$N"; else printf '%sSome checks failed. Fix them before starting.%s\n' "$R" "$N"; return 1; fi
}

start() {
  if pid=$(running_pid); then echo "Console already running (pid $pid): http://$HOST:$PORT"; return 0; fi
  check
  mkdir -p logs
  step "Starting console"
  FRAUDCLEF_UI_BACKEND=$BACKEND nohup uv run -q python -m uvicorn fraudclef.web.app:app --host "$HOST" --port "$PORT" >"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  for _ in $(seq 1 40); do
    if curl -fsS -m 1 "http://$HOST:$PORT/api/health" >/dev/null 2>&1; then
      ok "running on http://$HOST:$PORT (pid $(cat "$PID_FILE"), backend $BACKEND, log $LOG_FILE)"
      [[ $OPEN_BROWSER == 1 ]] && command -v open >/dev/null && open "http://$HOST:$PORT"
      return 0
    fi
    sleep 0.25
  done
  fail "console did not start; last log lines:"; tail -20 "$LOG_FILE"; return 1
}

stop() {
  if pid=$(running_pid); then
    # uv run spawns uvicorn as a child: stop the whole process group of children too.
    pkill -TERM -P "$pid" 2>/dev/null || true
    kill -TERM "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "Console stopped."
  else
    echo "Console is not running."
  fi
}

status() {
  if pid=$(running_pid); then
    echo "Running (pid $pid) on http://$HOST:$PORT"
    curl -fsS -m 2 "http://$HOST:$PORT/api/health" >/dev/null && echo "Health check: ok" || echo "Health check: not responding"
  else
    echo "Not running."
  fi
}

case "$CMD" in
  check) check ;;
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  *) echo "usage: $0 {check|start|stop|restart|status} [--skip-tests] [--no-open] [--port N] [--fake]" >&2; exit 2 ;;
esac
