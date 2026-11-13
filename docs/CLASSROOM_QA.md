# Classroom Questions and Answers

These answers describe the submitted implementation. Use the output from the live run when discussing PIDs, memory values, and elapsed time. The report's 3.175-second result is a recorded example.

## 1. What does your application do, and where does it run?

**Answer:** "It is a TCP client and server written in C. The client can request system information, send PING or ECHO, and request a short sleep. On this Windows computer, the C programs run inside the bundled Linux guest under QEMU. They use real Linux processes and sockets."

**Show:** [server.c](../src/server.c), [client.c](../src/client.c), and `uname -srmo` in the Linux terminal.

## 2. Why did you use fork instead of threads?

**Answer:** "The assignment requires fork. The parent accepts a connection and creates a separate child to serve it. Each child has its own process address space. This makes the process structure easy to demonstrate, but creating a process costs more resources than sharing work inside one process. I am not claiming that fork is always the fastest server design."

**Show:** Search for `fork()` in [server.c](../src/server.c). The C application does not create threads.

## 3. Why does the parent close the accepted socket, while the child closes the listening socket?

**Answer:** "After fork, both processes inherit descriptors for both sockets. The child only needs the connected socket, so it closes the listener. The parent only needs the listener, so it closes its copy of the connected socket. Closing one process's descriptor does not close the other process's inherited descriptor. This also avoids keeping unnecessary socket references open."

## 4. How do you prove that at least ten clients run concurrently?

**Answer:** "The demonstration starts twelve C client processes together. While their requests are still running, it checks that twelve worker processes exist under the same server parent PID. It then checks all twelve successful replies. The simultaneous process snapshot is the main proof; the elapsed time supports it."

**Run:**

```bash
python3 scripts/cli_evidence.py concurrency
```

The script prints the actual `ps --ppid` command and the twelve child rows. It starts and stops its own temporary server on port 19210.

## 5. Why use SLEEP 3000, and what does 3.175 seconds mean?

**Answer:** "A three-second sleep keeps the workers alive long enough to observe them together. In the recorded run, twelve requests completed in 3.175 seconds. Twelve sequential three-second waits would require at least 36 seconds, but that is a calculated lower bound, not a separate measured serial server. This is a concurrency demonstration, not a CPU performance benchmark. My new timing can differ under QEMU."

## 6. What belongs in the shared library? Does it provide shared memory?

**Answer:** "The library contains framing, socket helpers, logging, numeric validation, and time functions used by both programs. Both executables load the same libnetsys.so file. That does not mean their ordinary variables become shared memory. Each process still has its own state; the programs communicate through TCP."

**Show:** [netsys.h](../include/netsys.h) and [netsys.c](../src/netsys.c).

## 7. How do you prove that the library is dynamically linked?

**Answer:** "The Makefile compiles the library object with position-independent code and links it with the shared option. Both executables link against libnetsys. The ldd output shows the library dependency, and readelf shows the needed library and the runtime search path. ORIGIN makes the loader look beside the executable."

```bash
ldd build/debug/server
ldd build/debug/client
readelf -d build/debug/server | grep -E 'NEEDED.*libnetsys|RUNPATH'
readelf -d build/debug/client | grep -E 'NEEDED.*libnetsys|RUNPATH'
```

## 8. What does the Makefile build?

**Answer:** "It builds a server, a client, and libnetsys.so in separate debug and release directories. The debug build uses ENABLE_DEBUG=1 with debugging information. The release build uses ENABLE_DEBUG=0 and optimization. The shared header and library are declared as dependencies, so the executable targets are rebuilt when those dependencies change."

```bash
make DEBUG=1
make DEBUG=0
```

**Show:** [Makefile](../Makefile). `make clean` removes the generated build directory, not the source.

## 9. How are compile-time and runtime debug controls different?

**Answer:** "The compile-time macro determines whether NET_DEBUG calls are included. In a debug build, the runtime --debug flag determines whether those calls print. A release build cannot turn those calls back on with --debug. INFO, WARN, and ERROR messages can still appear because these controls specifically govern DEBUG messages."

**Run:**

```bash
python3 scripts/cli_evidence.py debug-library
```

The recorded four combinations produced 0, 8, 0, and 0 DEBUG lines. Client and server runtime flags are separate settings for their respective processes.

## 10. What is the message format, and why use network byte order?

**Answer:** "Each application frame starts with a four-byte unsigned payload length, followed by that many text bytes. The valid payload length is one to 4096 bytes. htonl and ntohl convert the length to and from network byte order, so the protocol does not depend on the machine's integer byte order. The terminating C string null byte is not sent."

**Example:** `PING` is `00 00 00 04 50 49 4e 47`: length four, then four command bytes.

## 11. Why can't you use one recv call for a complete request?

**Answer:** "TCP provides a byte stream, not application message boundaries. A receive call can return fewer bytes than requested. My robust receive loop accumulates the full header, validates the length, and then accumulates the body. The send function also loops until the complete frame is written, handling temporary readiness conditions and interruptions."

**Show:** `read_bytes`, `net_recv_frame`, and `net_send_frame` in [netsys.c](../src/netsys.c).

## 12. How exactly does the timeout work?

**Answer:** "Receiving a frame uses one absolute monotonic deadline shared by its header and body. Receiving a few bytes does not restart that deadline. Sending a frame has its own deadline. This is not a single deadline for all command execution: for example, SLEEP executes after the request has been received."

The default server receive/send timeout is 2000 ms. The idle comparison explicitly uses 500 ms. The client has its own timeout, which defaults to 5000 ms.

## 13. What happens with malformed input or a disconnected client?

**Answer:** "The receiver rejects zero or oversized lengths and embedded null bytes. A clean EOF before a new header is normal. An EOF partway through a frame is an error. The worker attempts a short error response where possible, closes its connection, and exits. A broken client should not take down the parent server."

**Examples:** `ERR BAD_LENGTH`, `ERR BAD_FRAME`, and `ERR TIMEOUT`. Command validation also rejects invalid SLEEP arguments and unknown commands.

## 14. Is there one child per request or one child per connection?

**Answer:** "There is one child per accepted connection. Its service loop can handle multiple framed requests on that connection until EOF, an error, or QUIT. The supplied command-line client normally sends one request, receives one reply, and closes, so its usual demonstration uses one request per connection."

## 15. Where does SYSINFO obtain its values?

**Answer:** "The server calls gethostname, uname, and Linux sysinfo. It reports the host name, kernel, architecture, worker PID, uptime, and memory information. In the offline demonstration these describe the Linux guest visible to the server, not the Windows host's complete hardware configuration."

**Run:**

```bash
./build/debug/client --port 9090 SYSINFO
```

This command requires the manual server on port 9090 to be running.

## 16. What are the three robustness comparisons?

**Answer:** "First, a PING frame is deliberately fragmented: the robust version reconstructs it, while the comparison version fails. Second, an idle connection is released by the deadline, while the comparison leaves a worker waiting. Third, completed children are reaped in robust mode, while the comparison leaves a zombie. The script applies the same input to each pair."

```bash
python3 scripts/cli_evidence.py robustness
```

The recorded results are successful PONG versus a broken connection, zero versus one idle worker, and zero versus one zombie. Error wording can vary across runs.

## 17. Does --unsafe disable every protection?

**Answer:** "No. It is a controlled comparison mode. It disables recovery from short receives, the idle receive deadline, and active child reaping while the server runs. Length checks and buffer bounds remain. Both modes still clean up their children when the server shuts down."

This avoids claiming that the comparison is a completely unprotected implementation.

## 18. What is a zombie, and how do you remove it?

**Answer:** "A zombie is a child that has exited but whose termination status has not yet been collected by its parent. The parent calls waitpid with WNOHANG in a loop, removes reaped PIDs from its active list, and continues accepting clients. The SIGCHLD handler does very little; the main loop performs the bookkeeping."

**Show:** `reap_children` in [server.c](../src/server.c). In the robustness output, `Z` is the zombie state; `S` is a sleeping or waiting worker.

## 19. What happens when you press Ctrl+C?

**Answer:** "The parent's signal handler sets a stop flag. The parent then closes the listener, terminates outstanding workers, and waits for them before exiting. Around fork, termination signals are temporarily blocked so a new child can restore its termination handlers before signals are delivered. This avoids a shutdown race."

For the complete Windows bundle, stop the manual server first, exit the Linux shells, and then use `STOP_LINUX.cmd` to power off the guest.

## 20. Can writing to a disconnected socket kill the process?

**Answer:** "A disconnected peer can cause a write error and may raise SIGPIPE. This program ignores SIGPIPE, and the send function also uses MSG_NOSIGNAL. It checks the send result and closes the failed connection instead of treating a successful write as guaranteed."

## 21. How many clients can the server accept, and what if fork fails?

**Answer:** "The application defaults to a maximum of 64 tracked clients, configurable up to the implementation's hard limit of 1024. The listen backlog is 128, which is a different concept from the active-worker cap. At the cap, or if fork fails, the server attempts ERR SERVER_BUSY and closes that accepted socket. Increasing a limit does not prove the computer can support that many clients. I have provided runtime proof for twelve."

**Show:** `--max-clients`, `CHILD_LIMIT`, and the fork error branch in [server.c](../src/server.c).

## 22. How was the packet capture obtained and analyzed?

**Answer:** "The test runs tcpdump on the Linux loopback interface and saves a real PCAP. TShark reads that file to show the handshake, request and response data, acknowledgments, and FIN packets. The submitted reference capture contains forty packets across four TCP connections, with no resets. A new capture may have different packet counts or sizes."

```bash
tshark -r evidence-cli/loopback.pcap -Y 'tcp.stream == 0'
tshark -r evidence-cli/loopback.pcap -Y 'tcp.len == 8 && tcp.dstport == 19090' -x
```

Reading the supplied PCAP does not need capture privileges. Making a fresh capture does; the offline guest already runs as root.

## 23. Is one application request always one TCP packet?

**Answer:** "No. Application frames and captured TCP segments are different units. TCP can split or combine the bytes differently. The receiver uses the length prefix and receive loops to recover the message. In this particular reference capture, SYSINFO has seven command bytes plus the four-byte prefix, so its request carries eleven TCP data bytes. The recorded reply carries 163 payload bytes plus its prefix, or 167 TCP data bytes."

Do not present those particular reply lengths as fixed protocol constants; system information and PIDs change.

## 24. What are the current limitations, and can it run between two computers?

**Answer:** "It is an IPv4 classroom demonstration. It defaults to loopback and has no TLS or user authentication. The host and port options allow a suitable IPv4 address, so a two-computer demonstration would also need reachable addresses and the network's permission to use that port. I would add authentication, encryption, and stronger resource controls before using it as a public service. The submitted loopback capture meets this assignment's allowed capture method."

The Windows launchers require the full desktop bundle. A plain GitHub clone contains the complete source, documentation, media, and reference evidence, but excludes QEMU, the Linux disk, and generated build artifacts. Use the README's native Linux or Docker instructions for a source-only clone.

The bundled QEMU configuration forwards only its SSH port on Windows loopback. Reaching the application from another computer would also require suitable guest networking or application-port forwarding; changing the C server's listening address alone is insufficient in that bundle.
