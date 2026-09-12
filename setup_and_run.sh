#!/usr/bin/env bash
# setup_and_run.sh — create venv, install deps, launch Let-It-Die TODO Tracker
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"
REQS="${PROJECT_DIR}/requirements.txt"
LAUNCHER="${PROJECT_DIR}/start_todo_tracker.py"

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --offscreen   Run headless (no GUI window, for servers/SSH)"
    echo "  --save PATH   Open a specific save file on launch"
    echo "  --help        Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                      # normal GUI launch"
    echo "  $0 --offscreen          # headless (QT_QPA_PLATFORM=offscreen)"
    echo "  $0 --save ~/Savedata/76561198140783693.sav"
    exit 0
}

OFFSCREEN=0
SAVE_ARG=""

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --offscreen) OFFSCREEN=1; shift ;;
        --save)      SAVE_ARG="--save '$2'"; shift 2 ;;
        --help)      usage ;;
        *)           echo "Unknown option: $1"; usage ;;
    esac
done

# --- create venv if missing ---
if [[ ! -d "$VENV_DIR" ]]; then
    echo ">> Creating virtual environment in ${VENV_DIR} ..."
    python3 -m venv "$VENV_DIR"
else
    echo ">> Virtual environment already exists at ${VENV_DIR}"
fi

# --- activate ---
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# --- upgrade pip (quiet) ---
echo ">> Ensuring pip is up to date ..."
pip install --quiet --upgrade pip

# --- install requirements ---
if [[ -f "$REQS" ]]; then
    echo ">> Installing requirements from ${REQS} ..."
    pip install --quiet -r "$REQS"
else
    echo "WARNING: ${REQS} not found — installing PySide6 only."
    pip install --quiet "PySide6>=6.5.0"
fi

# --- verify launcher exists ---
if [[ ! -f "$LAUNCHER" ]]; then
    echo "ERROR: Launcher not found: ${LAUNCHER}"
    exit 1
fi

# --- launch ---
echo ">> Launching TODO Tracker ..."
if [[ $OFFSCREEN -eq 1 ]]; then
    export QT_QPA_PLATFORM=offscreen
    echo "    (offscreen / headless mode)"
fi

PYTHON_CMD="${VENV_DIR}/bin/python"
if [[ -n "$SAVE_ARG" ]]; then
    exec "$PYTHON_CMD" "$LAUNCHER" $SAVE_ARG
else
    exec "$PYTHON_CMD" "$LAUNCHER"
fi
