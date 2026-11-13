# Classroom Demonstration

Use this guide for an approximately 8 to 10 minute live demonstration. The submitted English video is a separate 120-second walkthrough. Text in quotation marks is a suggested spoken English script; read the measured output on screen when it differs from the recorded examples.

The [command cheat sheet](CLASSROOM_COMMANDS.txt) contains the same workflow without the full narration. The [teacher Q&A](CLASSROOM_QA.md) explains the implementation in more detail.

## Before your presentation slot

Use the complete desktop bundle in `ForkSysInfo_Assignment/ForkSysInfo`, including `portable-linux/`.

1. Connect the laptop to power and allow enough time for the offline Linux VM to boot.
2. Double-click `START_DEMO.cmd`. Wait for **All runtime validation passed.** This builds both variants and runs the full suite. The VM remains running after the launcher window closes.
3. Open `report/ForkSysInfo_Report.pdf`, `media/diagrams/architecture.png`, and `media/diagrams/protocol.png` in Windows. Keep `media/ForkSysInfo_2min.mp4` available if the teacher asks to see it.
4. Open `LINUX_SHELL.cmd` twice. Put Terminal A on the left and Terminal B on the right. Both initially enter `/root/ForkSysInfo` in the same Linux VM.
5. Prepare the temporary classroom copy below and leave both terminals ready before you begin speaking. Use only one offline bundle at a time; its SSH forwarding port is 22222.

The launchers belong to the complete Windows bundle. A GitHub source download requires the native Linux or Docker setup in [README](../README.md). The offline guest already runs as root; do not add `sudo` to its commands. Native Linux needs capture privileges for a new tcpdump capture.

## Prepare one working copy for both terminals

The helper modes replace their `evidence-cli/` output. Use a fresh temporary copy so the report's submitted reference evidence remains unchanged. **Create it once in Terminal A**, not once in each terminal.

Terminal A:

```bash
cd /root/ForkSysInfo
CLASSDIR=$(mktemp -d /tmp/forksysinfo-classroom.XXXXXX)
cp -a include src tests scripts Makefile build evidence-cli "$CLASSDIR"/
printf '%s\n' "$CLASSDIR" > /tmp/forksysinfo-classroom.path
cd "$CLASSDIR"
pwd
```

Terminal B:

```bash
cd "$(cat /tmp/forksysinfo-classroom.path)"
pwd
```

The two `pwd` outputs must be identical. The path file only helps the second shell join the same copy. Recreate the temporary copy for a new rehearsal session; the submitted project stays in `/root/ForkSysInfo` and on the Windows desktop.

## 1. Introduce the design and build the programs — about 1 minute

Show the architecture diagram. Point to the parent, child processes, TCP connections, and shared library.

Say:

> This is ForkSysInfo, a TCP client and server written in C. The parent process accepts connections and calls fork to create one child for each client. Each child handles its own connected socket while the parent continues accepting connections. I do not use threads to handle clients. Both executables dynamically link the same shared utility library.

Terminal A, before starting the server:

```bash
make -B DEBUG=1 all
make -B DEBUG=0 all
```

Point to `-DENABLE_DEBUG`, `-fPIC`, `-shared`, and `-lnetsys` in the build output. Expected result: both commands finish without compiler errors; `build/debug/` and `build/release/` contain the client, server, and `libnetsys.so`.

Say:

> The Makefile creates separate debug and release directories. The common code is compiled as position-independent code and built into libnetsys.so. Both the client and server link against that library.

## 2. Run the server and request system information — about 1 minute

Terminal A:

```bash
./build/debug/server --host 127.0.0.1 --port 9090 --timeout-ms 5000 --max-clients 64 --debug
```

Leave it in the foreground. Wait for `READY`. Terminal B:

```bash
./build/debug/client --port 9090 SYSINFO
./build/debug/client --port 9090 --debug PING
./build/debug/client --port 9090 ECHO "Hello from the classroom"
```

Point to `OK SYSINFO`, Linux/kernel/memory fields, worker PIDs, and the `FORK` and `REAP` lines in Terminal A.

Say:

> The client requests system information from the server. This response describes the Linux environment where the server runs, including the kernel, architecture, memory, and uptime. PING returns a worker process ID, and ECHO returns the text I sent. The server log shows children being created and reaped.

Optional, if asked about invalid input:

```bash
./build/debug/client --port 9090 INVALID
./build/debug/client --port 9090 SLEEP -1
./build/debug/client --port 9090 PING
```

Expected: `ERR UNKNOWN_COMMAND`, `ERR BAD_ARGUMENT`, then a successful PONG. The two intentional error responses produce nonzero client exit codes.

Say:

> Invalid commands and arguments receive error responses. The server remains available for the next valid request.

Before the managed demonstrations, **press Ctrl+C in Terminal A**. Wait for `STOPPED active=0` and the shell prompt. Leave Terminal A open. Run the following modes one at a time in Terminal B; each starts and stops its own temporary servers on separate test ports.

## 3. Prove that twelve clients overlap — about 1 minute

Terminal B:

```bash
python3 scripts/cli_evidence.py concurrency
```

Point to twelve child-process rows with the same PPID, twelve `OK SLEPT 3000` replies, and the measured elapsed time.

Say:

> This command launches twelve real C clients. Each requests a three-second sleep. The process snapshot shows twelve children alive at the same time under one parent, and all twelve clients receive successful replies. The overlap is the main concurrency proof. The elapsed time provides additional evidence.

> The report records 3.175 seconds for its run. Process IDs and timings can change when I rerun it. Thirty-six seconds is the calculated serial waiting time for twelve three-second requests; I did not measure a separate serial server.

Do not describe a new PID as 2152 or promise that every run will take exactly 3.175 seconds. This demonstrates concurrent waiting and service, not a CPU throughput benchmark.

## 4. Compare three abnormal conditions — about 1 minute

Terminal B:

```bash
python3 scripts/cli_evidence.py robustness
```

Read the robust and unsafe columns together.

| Input or condition | Robust mode | Unsafe teaching mode |
|---|---|---|
| One PING frame sent in small fragments | Complete frame is read; PONG is returned | A short read is treated as failure; connection error |
| Idle connection; 500 ms receive deadline, inspected after 1.2 s | No active worker remains | One worker remains blocked |
| Completed client, inspected after 300 ms | No zombie remains | One zombie is visible |

Say:

> These are three paired comparisons using the same abnormal conditions. Full receive loops handle fragmented input. A receive deadline releases an idle connection. Reaping collects completed child processes. The unsafe teaching mode disables those three mechanisms so their effects are visible. It still keeps buffer-size checks; it is not a mode that disables every safeguard.

The exact connection-error wording and PIDs can vary. The helper stops its temporary servers after the comparisons.

## 5. Show the debug controls and shared-library linkage — about 1 minute

Terminal B:

```bash
python3 scripts/cli_evidence.py debug-library
```

Point to the four debug combinations, both `ldd` results, and the `$ORIGIN` RUNPATH.

Say:

> Debug output requires two controls. The program must be built with DEBUG equal to one, and it must also receive the runtime debug flag. A release build does not restore debug calls when I pass that flag. Normal information, warning, and error logs are separate from these debug messages.

> The linkage output confirms that both programs load libnetsys.so. The ORIGIN runpath lets each executable find the library beside itself, which also works in this temporary copy.

The recorded PING matrix is 0, 8, 0, 0 debug lines. Explain the enabled/disabled behavior rather than treating eight lines as a protocol guarantee.

## 6. Capture and inspect TCP traffic — about 1 to 2 minutes

To perform a fresh complete test and tcpdump capture in the temporary copy:

```bash
python3 scripts/cli_evidence.py suite
```

Keep the manual server stopped and do not start another test mode until this command finishes. Expected: `11/11 passed` and a fresh `evidence-cli/loopback.pcap`. This full suite uses `SLEEP 2000`; its concurrency timing is a different measurement from the separate `SLEEP 3000` demonstration above.

Say:

> This is a fresh integration run in the classroom copy. It rebuilds both variants, checks the features and abnormal conditions, and captures real loopback TCP traffic with tcpdump. The result should show all eleven test groups passing. These new files are separate from the evidence submitted with the report.

Show the protocol diagram, then inspect the capture:

```bash
python3 scripts/cli_evidence.py tshark
python3 scripts/cli_evidence.py tshark-hex
```

Point to the SYN/SYN-ACK/ACK exchange, data lengths, FIN exchange, and `0000000450494e47` in the hex output.

Say:

> TShark reads the capture created by tcpdump. The table shows connection establishment, data transfer, and orderly closing. Our application message begins with a four-byte length in network byte order. For PING, the length is four and the next four bytes spell PING.

> TCP is a byte stream. A send call, a receive call, and a captured TCP packet do not necessarily correspond to one application message. That is why the library reads the length header and then the required number of payload bytes.

If time is short, read the copied reference capture with the two TShark modes and run `python3 scripts/cli_evidence.py summary` to display the saved test status. Say explicitly that those are recorded results. Run the fresh suite when the teacher asks for a new capture; the video is supplementary and does not replace the live demonstration.

## 7. Close and invite questions — about 30 seconds

Say:

> This demonstrates the required fork-based server, concurrent clients, system information request, shared library, two debug controls, robustness comparisons, and packet analysis. The English report includes the design, screenshots, diagrams, and complete C source. The repository also includes the two-minute English video and reproduction instructions. I can now show the relevant source code or rerun a specific test.

After questions, stop any foreground manual server with Ctrl+C. Type `exit` in both Linux shells. In Windows, double-click `STOP_LINUX.cmd` and wait for the shutdown message.

## A three-minute version if the teacher limits the time

Prepare and build before your slot. Keep the two terminals and diagram open.

| Approximate time | Action | Short spoken line |
|---|---|---|
| 0:00 to 0:25 | Architecture diagram; start manual server | “The parent accepts connections and forks one child per client. Both programs link the shared library.” |
| 0:25 to 0:50 | SYSINFO and PING; stop manual server with Ctrl+C | “The client requests Linux system information. The logs show the worker processes handling requests.” |
| 0:50 to 1:25 | `python3 scripts/cli_evidence.py concurrency` | “Twelve C clients overlap. The same-parent process snapshot and successful replies prove concurrent service.” |
| 1:25 to 1:55 | `python3 scripts/cli_evidence.py robustness` | “These three pairs compare fragmented input, idle deadlines, and zombie reaping.” |
| 1:55 to 2:20 | `python3 scripts/cli_evidence.py debug-library` | “Both debug controls must be enabled. The linkage output confirms the shared library on both sides.” |
| 2:20 to 3:00 | Read reference TShark hex and saved summary | “This is the recorded capture and saved eleven-of-eleven result. I can generate fresh evidence if requested.” |

These timings are a rehearsal target, not a runtime guarantee. If the teacher requests a fresh capture or a full rerun, allow extra time.

## When something goes wrong

Use the troubleshooting section in [CLASSROOM_COMMANDS.txt](CLASSROOM_COMMANDS.txt). Keep the error visible, check the working directory and the server's port, and explain what you are correcting. Stop the specific server or test you started before retrying. Avoid starting several fixed-port test runs together.

Useful source locations for questions:

| Topic | File or function |
|---|---|
| Accept, fork, admission and shutdown | `src/server.c`, `main()` |
| Child request loop | `src/server.c`, `serve_client()` |
| Child collection | `src/server.c`, `reap_children()` |
| SYSINFO fields | `src/server.c`, `system_info()` |
| Framing, partial I/O, monotonic deadlines | `src/netsys.c`, `net_recv_frame()`, `net_send_frame()`, I/O helpers |
| Compile-time debug macro | `include/netsys.h`, `NET_DEBUG` |
| Client options and one-request behavior | `src/client.c`, `main()` |
| Shared library and linker flags | `Makefile` |
| Automated comparisons and packet parser | `tests/run_tests.py` |
| Short live demonstration modes | `scripts/cli_evidence.py` |
