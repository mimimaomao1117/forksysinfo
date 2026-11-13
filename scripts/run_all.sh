#!/bin/sh
# Run inside Linux with gcc, make, python3, tcpdump, iproute2 and binutils.
set -eu
cd "$(dirname "$0")/.."
lock=/tmp/forksysinfo-validation.lock
if ! mkdir "$lock" 2>/dev/null; then
    echo 'Another validation run is already using the fixed test ports.' >&2
    exit 2
fi
trap 'rmdir "$lock"' EXIT
python3 tests/run_tests.py
