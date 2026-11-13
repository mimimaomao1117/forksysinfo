#!/bin/sh
# Print a live demonstration on a Linux console or an ordinary terminal.
set -eu
cd "$(dirname "$0")/.."
printf '\033c'
echo 'ForkSysInfo - LIVE C CLIENT / FORK SERVER DEMONSTRATION'
uname -srmo
gcc --version | head -1
echo
./build/debug/server --port 19099 --timeout-ms 3000 > /tmp/forksysinfo-console-server.log 2>&1 &
parent=$!
trap 'kill "$parent" 2>/dev/null || true; wait "$parent" 2>/dev/null || true' EXIT
sleep 0.3
head -1 /tmp/forksysinfo-console-server.log
echo
echo '$ ./build/debug/client --port 19099 SYSINFO'
./build/debug/client --port 19099 SYSINFO
echo
echo '$ ./build/debug/client --port 19099 --debug PING'
./build/debug/client --port 19099 --debug PING
echo
echo '$ ./build/debug/client --port 19099 ECHO "Hello from C"'
./build/debug/client --port 19099 ECHO 'Hello from C'
echo
echo 'Both executables load the same dynamic library:'
ldd ./build/debug/client | grep libnetsys
ldd ./build/debug/server | grep libnetsys
echo
echo 'Live program execution completed successfully.'
