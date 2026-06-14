#!/usr/bin/env sh
# Àkàndé one-command installer.
#
# Quick install:
#   curl -fsSL https://akande.co/install.sh | sh
#
# What this does:
#   1. Detects the host OS and Python interpreter (3.10+).
#   2. Tries the strongly-preferred install paths in order:
#        a) pipx install akande         (the right answer on most machines)
#        b) uv tool install akande      (when uv is on PATH and pipx isn't)
#        c) python -m pip install --user akande  (last-resort fallback)
#   3. Reports the resolved install location and the next step.
#
# This script is intentionally POSIX-sh (not bash) so it runs on a stock
# macOS, Ubuntu, Alpine, or BusyBox shell without bashisms.  Run with
# `sh -n install.sh` to syntax-check, and `shellcheck install.sh` to lint.

set -eu

AKANDE_PACKAGE=${AKANDE_PACKAGE:-akande}
AKANDE_VERSION=${AKANDE_VERSION:-}
EXTRAS=${AKANDE_EXTRAS:-}

# --- ANSI helpers -----------------------------------------------------------

if [ -t 1 ]; then
    BOLD='\033[1m'; DIM='\033[2m'; CYAN='\033[36m'; GREEN='\033[32m'
    YELLOW='\033[33m'; RED='\033[31m'; RESET='\033[0m'
else
    BOLD=''; DIM=''; CYAN=''; GREEN=''; YELLOW=''; RED=''; RESET=''
fi

info()  { printf "%b\n" "${CYAN}→${RESET} $*"; }
ok()    { printf "%b\n" "${GREEN}✓${RESET} $*"; }
warn()  { printf "%b\n" "${YELLOW}⚠${RESET} $*" >&2; }
fail()  { printf "%b\n" "${RED}✗${RESET} $*" >&2; exit 1; }

spec() {
    # Renders the package spec, including any pinned version and extras.
    if [ -n "${EXTRAS}" ]; then
        printf "%s[%s]" "${AKANDE_PACKAGE}" "${EXTRAS}"
    else
        printf "%s" "${AKANDE_PACKAGE}"
    fi
    if [ -n "${AKANDE_VERSION}" ]; then
        printf "==%s" "${AKANDE_VERSION}"
    fi
}

# --- OS detection -----------------------------------------------------------

os_name() {
    case "$(uname -s 2>/dev/null || echo unknown)" in
        Darwin) echo macos ;;
        Linux)  echo linux ;;
        MINGW*|MSYS*|CYGWIN*) echo windows ;;
        *)      echo unknown ;;
    esac
}

OS="$(os_name)"
info "Detected OS: ${BOLD}${OS}${RESET}"

# --- prerequisites ---------------------------------------------------------

require_python() {
    if command -v python3 >/dev/null 2>&1; then
        PY=python3
    elif command -v python >/dev/null 2>&1; then
        PY=python
    else
        fail "Python 3.10+ is required but no python interpreter was found."
    fi
    if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then
        fail "Python 3.10+ required; found $(${PY} --version 2>&1)."
    fi
    info "Using $(${PY} --version 2>&1)"
}

system_deps_hint() {
    case "$OS" in
        macos)
            echo "  Run:  brew install portaudio ffmpeg"
            ;;
        linux)
            echo "  Run:  sudo apt install -y portaudio19-dev ffmpeg  # (Debian/Ubuntu)"
            ;;
        *)
            echo "  See https://akande.co/install for platform notes."
            ;;
    esac
}

require_python

# Hint about system deps without forcing an action — package managers vary.
info "Make sure PortAudio and ffmpeg are available:"
system_deps_hint

# --- install paths ---------------------------------------------------------

install_via_pipx() {
    info "Installing via ${BOLD}pipx${RESET}"
    pipx install "$(spec)"
}

install_via_uv() {
    info "Installing via ${BOLD}uv tool${RESET}"
    uv tool install "$(spec)"
}

install_via_pip_user() {
    info "Installing via ${BOLD}python -m pip --user${RESET}"
    "$PY" -m pip install --user --upgrade "$(spec)"
}

INSTALLED_VIA=""

if command -v pipx >/dev/null 2>&1; then
    install_via_pipx
    INSTALLED_VIA=pipx
elif command -v uv >/dev/null 2>&1; then
    install_via_uv
    INSTALLED_VIA=uv
else
    warn "Neither pipx nor uv found — falling back to 'python -m pip --user'."
    warn "Consider installing pipx (https://pipx.pypa.io) for cleaner upgrades."
    install_via_pip_user
    INSTALLED_VIA=pip
fi

ok "Àkàndé installed via ${INSTALLED_VIA}."

# --- verification ----------------------------------------------------------

if command -v akande >/dev/null 2>&1; then
    AKANDE_BIN="$(command -v akande)"
    ok "akande found at ${BOLD}${AKANDE_BIN}${RESET}"
else
    warn "akande is not on PATH after install."
    case "$INSTALLED_VIA" in
        pip)
            warn "Try:  ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
            ;;
        uv|pipx)
            warn "Try:  ${BOLD}${INSTALLED_VIA} ensurepath${RESET} and reopen your shell."
            ;;
    esac
fi

# --- next steps ------------------------------------------------------------

printf "\n"
printf "%b\n" "${DIM}Next:${RESET}"
printf "  ${CYAN}1.${RESET} cp .env.example .env  ${DIM}# set OPENAI_API_KEY or another provider${RESET}\n"
printf "  ${CYAN}2.${RESET} akande            ${DIM}# launch the TUI${RESET}\n"
printf "  ${CYAN}3.${RESET} ${DIM}or${RESET} akande install-local  ${DIM}# bootstrap the offline stack${RESET}\n"
printf "  ${CYAN}4.${RESET} ${DIM}or${RESET} akande mcp serve      ${DIM}# expose Àkàndé over MCP${RESET}\n"
