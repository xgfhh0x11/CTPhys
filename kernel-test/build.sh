#!/usr/bin/env bash
# Build the CTPhys phase binaries via the repo's Makefile.
#
# Usage: bash kernel-test/build.sh
# (from WSL: wsl -d Ubuntu-22.04 -- bash kernel-test/build.sh)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PHASES=(phase1_baseline phase3_no_cache phase4_no_store phase5_alu_contention)

if ! command -v gcc >/dev/null 2>&1; then
    echo "error: gcc not found in PATH." >&2
    echo "Install it with:" >&2
    echo "" >&2
    echo "    sudo apt-get update && sudo apt-get install -y build-essential" >&2
    echo "" >&2
    echo "(optionally also: sudo apt-get install -y linux-tools-generic linux-tools-common  # perf, best-effort under WSL2)" >&2
    exit 1
fi

echo "gcc found: $(gcc --version | head -1)"
echo "building phases from $REPO_DIR/src via $REPO_DIR/Makefile ..."

if ! make -C "$REPO_DIR" all; then
    echo "error: 'make all' failed -- see compiler output above." >&2
    exit 1
fi

missing=0
for p in "${PHASES[@]}"; do
    if [ -x "$REPO_DIR/build/$p" ]; then
        echo "  OK   build/$p"
    else
        echo "  MISSING build/$p" >&2
        missing=1
    fi
done

if [ "$missing" -ne 0 ]; then
    echo "error: build completed but not all expected binaries are present." >&2
    exit 1
fi

echo "build OK: ${PHASES[*]}"
