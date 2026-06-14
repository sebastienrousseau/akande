#!/usr/bin/env bash
#
# Àkàndé regression suite — validates a fully fresh install from a
# clean repo state.  Designed for the answer to the question "does
# this library actually operate end-to-end on someone else's box?"
#
# What this script does, in order:
#
#   1. Tears down any prior regression venv and starts from scratch.
#   2. Creates a new venv, upgrades pip / setuptools / wheel.
#   3. Installs the package with all runtime extras + dev tools + mcp.
#   4. Imports every public surface module (catches packaging
#      mistakes that pytest alone wouldn't surface).
#   5. Smoke-tests every CLI subcommand with --help.
#   6. Runs the four quality gates (pytest, mypy, bandit, pip-audit).
#   7. Prints a coloured pass/fail summary keyed by phase number so
#      a failure tells you exactly which step regressed.
#
# Usage:
#   ./scripts/regression.sh                # tear down venv on exit
#   ./scripts/regression.sh --keep-venv    # leave venv for inspection
#   ./scripts/regression.sh --skip-gates   # only verify install + smoke
#
# Exit codes:
#   0    All phases passed.
#   1    A phase failed; check the per-phase log for the cause.
#   2    Caller invoked the script wrong (unknown flag / missing python3).

set -euo pipefail

# --- config -----------------------------------------------------------------

VENV_DIR=".venv-regression"
LOG_DIR=".regression-logs"
KEEP_VENV=false
SKIP_GATES=false

for arg in "$@"; do
  case "$arg" in
    --keep-venv)  KEEP_VENV=true ;;
    --skip-gates) SKIP_GATES=true ;;
    --help|-h)
      sed -n '2,30p' "$0"
      exit 0
      ;;
    *)
      printf "unknown flag: %s\n" "$arg" >&2
      exit 2
      ;;
  esac
done

# --- pretty output ----------------------------------------------------------

if [ -t 1 ]; then
  BOLD=$'\033[1m'
  DIM=$'\033[2m'
  CYAN=$'\033[36m'
  GREEN=$'\033[32m'
  RED=$'\033[31m'
  YELLOW=$'\033[33m'
  RESET=$'\033[0m'
else
  BOLD=''
  DIM=''
  CYAN=''
  GREEN=''
  RED=''
  YELLOW=''
  RESET=''
fi

CURRENT_PHASE="setup"

phase() {
  CURRENT_PHASE="$1"
  printf "\n%s▶ Phase %s: %s%s\n" \
    "$BOLD$CYAN" "$1" "$2" "$RESET"
}

ok()   { printf "  %s✓%s %s\n" "$GREEN" "$RESET" "$1"; }
warn() { printf "  %s⚠%s %s\n" "$YELLOW" "$RESET" "$1" >&2; }
fail() { printf "  %s✗%s %s\n" "$RED" "$RESET" "$1" >&2; exit 1; }

# --- cleanup on exit --------------------------------------------------------

on_exit() {
  local code=$?
  if [ "$code" -ne 0 ]; then
    printf "\n%sRegression FAILED at phase %s%s\n" \
      "$RED$BOLD" "$CURRENT_PHASE" "$RESET" >&2
    printf "%sLogs under %s/%s\n" \
      "$DIM" "$LOG_DIR" "$RESET" >&2
  fi
  if ! $KEEP_VENV && [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
  fi
}
trap on_exit EXIT

# --- locate repo root + python ----------------------------------------------

cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  printf "python3 not found on PATH\n" >&2
  exit 2
fi

mkdir -p "$LOG_DIR"

# --- phase 1: fresh venv ----------------------------------------------------

phase 1 "Fresh virtual environment"
rm -rf "$VENV_DIR"
python3 -m venv "$VENV_DIR" >"$LOG_DIR/01-venv.log" 2>&1 \
  || fail "venv creation failed (see $LOG_DIR/01-venv.log)"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
PY_VERSION="$(python --version 2>&1)"
ok "created $VENV_DIR ($PY_VERSION)"

# --- phase 2: install -------------------------------------------------------

phase 2 "Install package + extras"
pip install --upgrade --quiet pip setuptools wheel \
  >"$LOG_DIR/02-pip-upgrade.log" 2>&1 \
  || fail "pip upgrade failed"
ok "upgraded pip / setuptools / wheel"

pip install --quiet -e ".[all,dev]" mcp \
  >"$LOG_DIR/02-install.log" 2>&1 \
  || fail "editable install failed (see $LOG_DIR/02-install.log)"
ok "installed akande[all,dev] + mcp"

# --- phase 3: import smoke --------------------------------------------------

phase 3 "Public-API import smoke test"
python -m tests.smoke_imports >"$LOG_DIR/03-imports.log" 2>&1 \
  || fail "public-API import smoke failed (see $LOG_DIR/03-imports.log)"
ok "every public module imports cleanly"

# --- phase 4: CLI smoke -----------------------------------------------------

phase 4 "CLI subcommand smoke test"

cli_help() {
  local label="$1"
  shift
  if python -m akande "$@" --help \
       >"$LOG_DIR/04-cli-$label.log" 2>&1; then
    ok "$label --help responded"
  else
    fail "$label --help did NOT respond (see $LOG_DIR/04-cli-$label.log)"
  fi
}

# Top-level argparse parses --help even when no subcommand is given.
cli_help "top"
cli_help "data" data
cli_help "verify-audit" verify-audit
cli_help "verify-watermark" verify-watermark
cli_help "mcp" mcp
cli_help "skill" skill
cli_help "install-local" install-local

# --- phase 5: quality gates -------------------------------------------------

if $SKIP_GATES; then
  warn "skipping quality gates (--skip-gates)"
else
  phase 5 "Quality gates"

  pytest -q --cov=akande --cov-fail-under=63 \
    >"$LOG_DIR/05-pytest.log" 2>&1 \
    || fail "pytest failed (see $LOG_DIR/05-pytest.log)"
  ok "pytest passed at >=63% coverage"

  mypy akande >"$LOG_DIR/05-mypy.log" 2>&1 \
    || fail "mypy failed (see $LOG_DIR/05-mypy.log)"
  ok "mypy clean"

  bandit -r akande -ll -q >"$LOG_DIR/05-bandit.log" 2>&1 \
    || fail "bandit failed (see $LOG_DIR/05-bandit.log)"
  ok "bandit: 0 medium+ findings"

  pip-audit --strict >"$LOG_DIR/05-pip-audit.log" 2>&1 \
    || fail "pip-audit failed (see $LOG_DIR/05-pip-audit.log)"
  ok "pip-audit: 0 known CVEs"
fi

# --- summary ----------------------------------------------------------------

phase 6 "Summary"
printf "\n%s%s  Fresh-install regression: %sALL PHASES PASSED%s\n\n" \
  "$BOLD" "$GREEN" "$GREEN" "$RESET"
printf "%sVenv:%s     %s\n" "$DIM" "$RESET" \
  "$( $KEEP_VENV && echo "$PWD/$VENV_DIR (kept)" || echo "torn down" )"
printf "%sLogs:%s     %s/\n" "$DIM" "$RESET" "$LOG_DIR"
printf "%sNext:%s     git add -A && git commit -S\n\n" \
  "$DIM" "$RESET"
