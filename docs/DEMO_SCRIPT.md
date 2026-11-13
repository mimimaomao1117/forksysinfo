# Demonstration Guide

Repository: https://github.com/mimimaomao1117/forksysinfo

The current lab report is in English and uses native Linux console screenshots. It includes diagrams of the parent and child processes, dynamic linking, and the length-prefixed protocol. The new console records are in `evidence-cli/`.

## Live demonstration

Build the project, start the server in one terminal, and run the client in another:

```bash
make DEBUG=1
./build/debug/server --port 9090 --debug
```

```bash
./build/debug/client --port 9090 SYSINFO
./build/debug/client --port 9090 PING
./build/debug/client --port 9090 ECHO "Hello from C"
```

Explain which process accepts connections and which child handles each client. Show `ldd build/debug/server` and `ldd build/debug/client` to verify that both load `libnetsys.so`.

Run `python3 scripts/cli_evidence.py concurrency` to launch twelve clients requesting SLEEP 3000. Point to the twelve children in the process snapshot before showing the completed replies. Then run the robustness and debug-library modes to demonstrate the three paired abnormal conditions and the two debug controls.

For a new complete test and packet capture, run `sudo python3 scripts/cli_evidence.py suite` on native Linux. In the offline guest or a capture-enabled container already running as root, sudo is unnecessary. Inspect the resulting capture with:

```bash
tshark -r evidence-cli/loopback.pcap -Y 'tcp.stream == 0'
tshark -r evidence-cli/loopback.pcap -Y 'tcp.len == 8 && tcp.dstport == 19090' -x
```

## Submitted two-minute video

`media/ForkSysInfo_2min.mp4` retains the original Traditional Chinese narration. Its SRT and transcript preserve the recorded wording. The video illustrates the earlier SLEEP 2000 reference run; its 2.141-second value is separate from the current report's SLEEP 3000 console demonstration at 3.175 seconds.

| Video time | Topic |
|---|---|
| 00:00 to 00:15 | Project and test result |
| 00:15 to 00:30 | Shared library and framing |
| 00:30 to 00:45 | System information request |
| 00:45 to 01:05 | Twelve simultaneous clients |
| 01:05 to 01:25 | Three robustness comparisons |
| 01:25 to 01:40 | Compile-time and runtime debug |
| 01:40 to 01:55 | Packet capture and payload |
| 01:55 to 02:00 | Reproduction entry point |

The Windows CMD entry points require the complete desktop bundle with `portable-linux/`. A GitHub clone uses the Linux or Docker instructions in README.md. For the desktop bundle, open two `LINUX_SHELL.cmd` windows and run `sh scripts/demo.sh --server` and `sh scripts/demo.sh`. Finish with `STOP_LINUX.cmd`.
