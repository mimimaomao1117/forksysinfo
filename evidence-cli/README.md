# Command Line Test Records

This directory contains a new run on Linux 6.12.117-0-virt under QEMU. The console screenshots used by the English lab report are in `../media/cli/`.

`results.json` is the complete integration suite result: 11 of 11 test groups passed. `console_results.json` indexes the separate console demonstrations. The standalone concurrency demonstration uses twelve C clients requesting SLEEP 3000, observes twelve server workers at one time, and completes in 3.175 seconds. Its 36-second sequential waiting figure is a theoretical lower bound, not a measured sequential implementation.

The suite creates a separate set of processes and uses SLEEP 2000 for its concurrency check. Its PIDs and timings must not be substituted for those in the standalone screenshot.

`loopback.pcap` was captured with tcpdump on the guest's `lo` interface. It contains four TCP connections and forty packets. TShark 4.4.7 was run in that Linux guest to inspect the saved capture. The PING payload is `0000000450494e47`: a four-byte length of 4 followed by the ASCII bytes for PING.

The `raw/console_*.txt` files preserve the output of each console demonstration. `screenshots.json` records the SHA-256 checksum, dimensions, mode, time and transcript for each native framebuffer capture. Full PNG files are unchanged; the PDF display omits only unused terminal space below the output.

To repeat the demonstrations in a Linux environment with the required tools:

```bash
sudo python3 scripts/cli_evidence.py suite
sudo python3 scripts/cli_evidence.py build
sudo python3 scripts/cli_evidence.py sysinfo
sudo python3 scripts/cli_evidence.py concurrency
sudo python3 scripts/cli_evidence.py robustness
sudo python3 scripts/cli_evidence.py debug-library
sudo python3 scripts/cli_evidence.py tshark
sudo python3 scripts/cli_evidence.py tshark-hex
```

The suite needs packet-capture permission. The C program itself needs no elevated privileges. Repeated runs update this directory; use a separate working copy if the submitted records must be preserved.
