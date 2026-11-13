# Demonstration Guide

Repository: https://github.com/mimimaomao1117/forksysinfo

For the complete two-terminal classroom workflow, use [CLASSROOM_DEMO.md](CLASSROOM_DEMO.md). It includes exact commands, an 8 to 10 minute spoken English script, a shorter route, and rehearsal preparation. Keep [CLASSROOM_COMMANDS.txt](CLASSROOM_COMMANDS.txt) beside the terminal; use [CLASSROOM_QA.md](CLASSROOM_QA.md) for 24 likely teacher questions and English answers.

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

`media/ForkSysInfo_2min.mp4` is an English narrated walkthrough of the current report's screenshots and diagrams. English subtitles are in `media/ForkSysInfo_2min.en.srt`; the narration text is in `media/ForkSysInfo_2min_transcript.txt`. It presents the recorded evidence rather than a new live execution.

| Video time | Topic |
|---|---|
| 00:00 to 00:10 | Project and debug/release builds |
| 00:10 to 00:25 | Parent, forked workers and shared-library diagram |
| 00:25 to 00:39 | Length-prefixed protocol diagram |
| 00:39 to 00:51 | SYSINFO, PING and ECHO output |
| 00:51 to 01:08 | Twelve simultaneous clients and 3.175-second result |
| 01:08 to 01:28 | Fragmented input, idle timeout and zombie comparisons |
| 01:28 to 01:40 | Compile-time/runtime debug and dynamic linking |
| 01:40 to 01:52 | TShark packet analysis and PING hex |
| 01:52 to 02:00 | 11/11 integration result and source location |

The concurrency screenshot shows twelve workers under parent PID 2152. All twelve C clients sent `SLEEP 3000` and succeeded in 3.175 seconds. A serial lower bound of 36 seconds is calculated from twelve three-second waits, not measured from a separate serial server. PIDs and timings change when rerun.

The robustness evidence compares full receive loops with fragmented-input failure, a 500 ms idle deadline with a worker still blocked after 1.2 seconds, and child reaping with a zombie child. The four debug combinations produce 0, 8, 0 and 0 debug lines in the recorded PING test. TShark 4.4.7 reads the current forty-packet capture with four TCP connections; the PING frame is `0000000450494e47`.

The Windows CMD entry points require the complete desktop bundle with `portable-linux/`. A GitHub clone uses the Linux or Docker instructions in README.md. For the desktop bundle, open two `LINUX_SHELL.cmd` windows and run `sh scripts/demo.sh --server` and `sh scripts/demo.sh`. Finish with `STOP_LINUX.cmd`.
