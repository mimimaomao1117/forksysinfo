#!/bin/sh
# Classroom demonstration. Run a separate server terminal first, or use --server.
set -eu
cd "$(dirname "$0")/.."
make DEBUG=1 all
if [ "${1:-}" = "--server" ]; then
    exec ./build/debug/server --host 127.0.0.1 --port 9090 --timeout-ms 3000 --debug
fi
./build/debug/client --port 9090 SYSINFO
./build/debug/client --port 9090 --debug PING
./build/debug/client --port 9090 ECHO "Hello from the classroom"
echo 'Starting 12 C clients concurrently; each child sleeps for 2 seconds.'
i=0
while [ "$i" -lt 12 ]; do
    ./build/debug/client --port 9090 SLEEP 2000 &
    i=$((i + 1))
done
sleep 0.3
ps -eo pid,ppid,stat,comm,args --forest
wait
echo 'All twelve clients finished. Full reproducible evidence: sh scripts/run_all.sh'
