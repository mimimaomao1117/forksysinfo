#!/usr/bin/env python3
"""Real Linux integration tests and evidence capture. Standard library only."""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
RAW = EVIDENCE / "raw"
RESULTS = {"tests": [], "robustness": {}, "concurrency": {}, "packet_capture": {}}
SERVERS = []


def save(name, content):
    path = RAW / name
    path.write_text(str(content), encoding="utf-8")
    return path


def run(args, timeout=15, check=True):
    result = subprocess.run([str(x) for x in args], cwd=ROOT,
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    if check and result.returncode:
        raise AssertionError(f"{args}: rc={result.returncode}\n{result.stdout}\n{result.stderr}")
    return result


def test(name, func):
    started = time.monotonic()
    try:
        detail = func()
        entry = {"name": name, "passed": True, "detail": detail}
        print(f"PASS {name}", flush=True)
    except Exception as exc:
        entry = {"name": name, "passed": False, "error": str(exc),
                 "traceback": traceback.format_exc()}
        print(f"FAIL {name}: {exc}", flush=True)
    entry["seconds"] = round(time.monotonic() - started, 3)
    RESULTS["tests"].append(entry)
    write_results()


def write_results():
    RESULTS["passed"] = all(x["passed"] for x in RESULTS["tests"])
    RESULTS["pass_count"] = sum(x["passed"] for x in RESULTS["tests"])
    RESULTS["test_count"] = len(RESULTS["tests"])
    (EVIDENCE / "results.json").write_text(
        json.dumps(RESULTS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def children(pid):
    try:
        ids = Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
    except FileNotFoundError:
        return []
    records = []
    for child in ids:
        try:
            stat = Path(f"/proc/{child}/stat").read_text()
            tail = stat[stat.rfind(")") + 2:].split()
            records.append({"pid": int(child), "ppid": int(tail[1]), "state": tail[0],
                            "command": Path(f"/proc/{child}/comm").read_text().strip()})
        except FileNotFoundError:
            pass
    return records


def wait_for(predicate, timeout=3):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        result = predicate()
        if result:
            return result
        time.sleep(0.025)
    return predicate()


class Server:
    def __init__(self, name, port, unsafe=False, timeout_ms=700,
                 debug=False, variant="debug", max_clients=64):
        self.path = RAW / f"{name}_server.log"
        self.handle = self.path.open("w", encoding="utf-8")
        self.port = port
        self.args = [ROOT / "build" / variant / "server", "--host", "127.0.0.1",
                     "--port", str(port), "--timeout-ms", str(timeout_ms),
                     "--max-clients", str(max_clients)]
        if unsafe:
            self.args.append("--unsafe")
        if debug:
            self.args.append("--debug")
        self.proc = subprocess.Popen([str(a) for a in self.args], cwd=ROOT,
                                     stdout=self.handle, stderr=self.handle,
                                     start_new_session=True)
        SERVERS.append(self)
        ready = wait_for(lambda: "READY" in self.path.read_text() or self.proc.poll() is not None, 5)
        if not ready or self.proc.poll() is not None:
            self.stop()
            raise AssertionError(f"Server failed to start: {self.path.read_text()}")

    @property
    def pid(self):
        return self.proc.pid

    def connect(self):
        return socket.create_connection(("127.0.0.1", self.port), timeout=3)

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait(timeout=3)
        self.handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stop()


def client(port, command, *args, debug=False, variant="debug", check=True):
    argv = [ROOT / "build" / variant / "client", "--host", "127.0.0.1",
            "--port", port, "--timeout-ms", "5000"]
    if debug:
        argv.append("--debug")
    return run(argv + [command] + list(args), check=check)


def read_exact(sock, size):
    result = b""
    while len(result) < size:
        part = sock.recv(size - len(result))
        if not part:
            raise EOFError(f"closed after {len(result)}/{size} bytes")
        result += part
    return result


def recv_frame(sock):
    size, = struct.unpack("!I", read_exact(sock, 4))
    if not 1 <= size <= 4096:
        raise AssertionError(f"Invalid response length {size}")
    return read_exact(sock, size).decode("utf-8")


def send_frame(sock, text):
    payload = text.encode()
    sock.sendall(struct.pack("!I", len(payload)) + payload)
    return recv_frame(sock)


def environment():
    outputs = []
    for args in (["uname", "-a"], ["gcc", "--version"], ["make", "--version"],
                 ["python3", "--version"], ["tcpdump", "--version"],
                 ["id"], ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"]):
        result = run(args)
        outputs.append("$ " + " ".join(args) + "\n" + result.stdout + result.stderr)
    save("environment.txt", "\n".join(outputs))
    RESULTS["environment"] = {"platform": run(["uname", "-a"]).stdout.strip(),
                               "python": sys.version, "uid": os.getuid(),
                               "utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    return "Linux toolchain and tcpdump present; versions recorded"


def build():
    text = []
    for variant in (1, 0):
        result = run(["make", "-B", f"DEBUG={variant}", "all"], timeout=90)
        text.append(f"$ make -B DEBUG={variant} all\n" + result.stdout + result.stderr)
    save("build.txt", "\n".join(text))
    return "DEBUG=1 and DEBUG=0 built successfully"


def normal_and_exceptional():
    transcript = []
    with Server("normal", 19091) as server:
        for command, args in (("SYSINFO", []), ("PING", []), ("ECHO", ["hello shared library"]),
                              ("SLEEP", ["20"])):
            result = client(server.port, command, *args)
            transcript.append(f"$ client {command} {' '.join(args)}\n{result.stdout}{result.stderr}")
            assert result.stdout.startswith("OK"), result.stdout
            if command == "SYSINFO":
                for field in ("hostname=", "sysname=Linux", "pid=", "uptime_seconds=", "ram_total_bytes="):
                    assert field in result.stdout, (field, result.stdout)
        with server.connect() as sock:
            for payload in ("NO_SUCH_COMMAND", "SLEEP -1", "SLEEP 999999", "SLEEP 12x"):
                response = send_frame(sock, payload)
                transcript.append(f"request={payload!r}\nresponse={response!r}")
                assert response.startswith("ERR"), response
        for length in (0, 4097, 0xFFFFFFFF):
            with server.connect() as sock:
                sock.sendall(struct.pack("!I", length))
                try:
                    response = recv_frame(sock)
                except (EOFError, ConnectionResetError):
                    response = "connection closed"
                transcript.append(f"invalid length={length}: {response}")
                assert not response.startswith("OK"), response
        with server.connect() as sock:
            sock.sendall(struct.pack("!I", 20) + b"EC")
            sock.shutdown(socket.SHUT_WR)
            try:
                response = recv_frame(sock)
            except (EOFError, ConnectionResetError):
                response = "connection closed"
            transcript.append("truncated payload then EOF: " + response)
        with server.connect() as sock:
            response = send_frame(sock, "ECHO " + "a" * 4091)
            assert response == "OK " + "a" * 4091
            transcript.append(f"maximum 4096-byte request accepted; response bytes={len(response)}")
        with server.connect() as sock:
            # TCP may coalesce multiple application frames into one receive.
            sock.sendall(struct.pack("!I", 4) + b"PING" + struct.pack("!I", 4) + b"QUIT")
            first, second = recv_frame(sock), recv_frame(sock)
            assert first.startswith("OK PONG") and second == "OK BYE"
            transcript.append(f"coalesced PING + QUIT: {first}; {second}")
        with server.connect() as sock:
            sock.sendall(struct.pack("!I", 5) + b"PI\x00NG")
            response = recv_frame(sock)
            assert response.startswith("ERR")
            transcript.append("embedded NUL rejected: " + response)
        with server.connect() as sock:
            sock.sendall(struct.pack("!I", 9) + b"SLEEP 100")
            # Force an immediate reset while the worker is preparing a response.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        time.sleep(0.2)
        transcript.append("reset peer during SLEEP; parent remains available")
        result = client(server.port, "PING")
        assert "PONG" in result.stdout
        transcript.append("server survived malformed clients: " + result.stdout)
        # A second listener must fail without disturbing the running server.
        duplicate = run([ROOT / "build/debug/server", "--host", "127.0.0.1",
                         "--port", server.port], check=False)
        assert duplicate.returncode != 0
        transcript.append(f"occupied port exit={duplicate.returncode}\n{duplicate.stderr}")
    refused = client(19091, "PING", check=False)
    assert refused.returncode != 0
    transcript.append(f"connection refused exit={refused.returncode}\n{refused.stderr}")
    save("normal_and_exceptional.txt", "\n".join(transcript))
    return "SYSINFO PING ECHO SLEEP; bad command/argument/length, partial EOF, occupied port, refused connection"


def concurrency():
    count, sleep_ms = 12, 2000
    procs = []
    with Server("concurrency", 19092, timeout_ms=6000) as server:
        begin = time.monotonic()
        try:
            for i in range(count):
                procs.append(subprocess.Popen(
                    [str(ROOT / "build/debug/client"), "--host", "127.0.0.1", "--port", str(server.port),
                     "--timeout-ms", "7000", "SLEEP", str(sleep_ms)], cwd=ROOT,
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            peak = []
            samples = []
            deadline = time.monotonic() + 1.5
            while time.monotonic() < deadline:
                observed = [c for c in children(server.pid) if c["state"] != "Z"]
                samples.append({"elapsed": round(time.monotonic() - begin, 4), "children": observed})
                if len(observed) > len(peak):
                    peak = observed
                if len(peak) >= count:
                    break
                time.sleep(0.01)
            ss = run(["ss", "-tnp"]).stdout
            ps = run(["ps", "-eo", "pid,ppid,stat,comm,args", "--forest"]).stdout
            save("concurrency_ss.txt", ss)
            save("concurrency_processes.txt", ps)
            save("concurrency_samples.json", json.dumps(samples, indent=2))
            outputs = []
            for index, proc in enumerate(procs):
                stdout, stderr = proc.communicate(timeout=10)
                outputs.append({"client_index": index + 1, "client_pid": proc.pid,
                                "exit_code": proc.returncode, "stdout": stdout, "stderr": stderr})
            elapsed = time.monotonic() - begin
            data = {"client_count": count, "sleep_ms": sleep_ms, "parent_pid": server.pid,
                    "simultaneous_child_count": len(peak), "simultaneous_children": peak,
                    "elapsed_seconds": round(elapsed, 3),
                    "serial_sleep_seconds": count * sleep_ms / 1000,
                    "clients": outputs}
            RESULTS["concurrency"] = data
            save("concurrency.txt", json.dumps(data, indent=2))
            assert len(peak) >= count, f"only {len(peak)} live children observed"
            assert all(x["exit_code"] == 0 and "OK SLEPT" in x["stdout"] for x in outputs), outputs
            assert elapsed < 8, f"concurrency took {elapsed:.2f}s, serial baseline 24s"
            assert wait_for(lambda: len(children(server.pid)) == 0, 3), children(server.pid)
            return {"simultaneous_children": len(peak), "wall_seconds": round(elapsed, 3), "serial_seconds": 24}
        finally:
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()


def fragmented_comparison():
    rows = []
    for offset, unsafe in enumerate((False, True)):
        mode = "unsafe" if unsafe else "robust"
        with Server(f"fragment_{mode}", 19093 + offset, unsafe=unsafe) as server:
            with server.connect() as sock:
                packet = struct.pack("!I", 4) + b"PING"
                sock.sendall(packet[:1])
                time.sleep(0.15)
                try:
                    sock.sendall(packet[1:3])
                    time.sleep(0.1)
                    sock.sendall(packet[3:])
                    response = recv_frame(sock)
                except (OSError, EOFError) as exc:
                    response = f"{type(exc).__name__}: {exc}"
                row = {"mode": mode, "fragments": [1, 2, 5], "response": response}
                rows.append(row)
                assert (response.startswith("OK PONG")) == (not unsafe), row
    RESULTS["robustness"]["fragmented_header"] = rows
    save("robustness_fragmented.txt", json.dumps(rows, indent=2))
    return rows


def idle_comparison():
    rows = []
    for offset, unsafe in enumerate((False, True)):
        mode = "unsafe" if unsafe else "robust"
        with Server(f"idle_{mode}", 19095 + offset, unsafe=unsafe, timeout_ms=500) as server:
            with server.connect() as sock:
                assert wait_for(lambda: children(server.pid), 1), "child not created"
                first = children(server.pid)
                begin = time.monotonic()
                # No bytes sent: naive blocking recv retains the unsafe child indefinitely.
                time.sleep(1.2)
                after = children(server.pid)
                active = [c for c in after if c["state"] != "Z"]
                row = {"mode": mode, "timeout_ms": 500,
                       "observed_after_seconds": round(time.monotonic() - begin, 3),
                       "before": first, "after": after, "active_children": len(active)}
                rows.append(row)
                assert len(active) == (1 if unsafe else 0), row
    RESULTS["robustness"]["idle_timeout"] = rows
    save("robustness_idle.txt", json.dumps(rows, indent=2))
    return rows


def zombie_comparison():
    rows = []
    for offset, unsafe in enumerate((False, True)):
        mode = "unsafe" if unsafe else "robust"
        with Server(f"zombie_{mode}", 19097 + offset, unsafe=unsafe) as server:
            result = client(server.port, "PING")
            assert "PONG" in result.stdout
            time.sleep(0.3)
            observed = children(server.pid)
            zombies = [c for c in observed if c["state"] == "Z"]
            row = {"mode": mode, "parent_pid": server.pid, "children": observed,
                   "zombie_count": len(zombies), "client_output": result.stdout.strip()}
            rows.append(row)
            assert len(zombies) == (1 if unsafe else 0), row
    RESULTS["robustness"]["zombie_reaping"] = rows
    save("robustness_zombies.txt", json.dumps(rows, indent=2))
    return rows


def admission_limit():
    with Server("admission", 19099, timeout_ms=2500, max_clients=2) as server:
        held = [server.connect(), server.connect()]
        try:
            assert wait_for(lambda: len(children(server.pid)) == 2), children(server.pid)
            with server.connect() as third:
                try:
                    response = recv_frame(third)
                except (EOFError, OSError) as exc:
                    response = str(exc)
                assert "BUSY" in response or not response.startswith("OK"), response
            observed = children(server.pid)
            assert len(observed) <= 2
            save("admission.txt", f"max_clients=2\nthird_client={response}\nchildren={observed}\n")
            return {"max_clients": 2, "third_client": response, "children": observed}
        finally:
            for sock in held:
                sock.close()


def debug_matrix():
    rows, transcript = [], []
    for index, (variant, runtime) in enumerate((("debug", False), ("debug", True),
                                               ("release", False), ("release", True))):
        with Server(f"debug_{variant}_{int(runtime)}", 19100 + index,
                    debug=runtime, variant=variant) as server:
            result = client(server.port, "PING", debug=runtime, variant=variant)
            assert "PONG" in result.stdout
        logs = server.path.read_text() + result.stderr
        lines = [line for line in logs.splitlines() if "DEBUG " in line]
        row = {"compile_debug": 1 if variant == "debug" else 0,
               "runtime_debug": runtime, "debug_line_count": len(lines)}
        assert bool(lines) == (variant == "debug" and runtime), (row, logs)
        rows.append(row)
        transcript.append(json.dumps(row) + "\n" + logs)
    RESULTS["debug_matrix"] = rows
    save("debug_matrix.txt", "\n".join(transcript))
    return rows


def shared_library():
    outputs = []
    for binary in ("server", "client"):
        target = ROOT / "build/debug" / binary
        linked = run(["ldd", target]).stdout
        dynamic = run(["readelf", "-d", target]).stdout
        assert "libnetsys.so" in linked and "not found" not in linked
        assert "libnetsys.so" in dynamic and "$ORIGIN" in dynamic
        outputs.append(f"$ ldd build/debug/{binary}\n{linked}\n$ readelf -d build/debug/{binary}\n{dynamic}")
    symbols = run(["nm", "-D", "--defined-only", ROOT / "build/debug/libnetsys.so"]).stdout
    outputs.append("$ nm -D --defined-only build/debug/libnetsys.so\n" + symbols)
    save("shared_library.txt", "\n".join(outputs))
    return "Both server and client have DT_NEEDED libnetsys.so and ORIGIN runtime search path"


def parse_pcap(path, server_port):
    blob = path.read_bytes()
    assert len(blob) >= 24, "pcap global header missing"
    magic = blob[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
        endian = "<"
    elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
        endian = ">"
    else:
        raise AssertionError(f"Unsupported pcap magic {magic.hex()}")
    nanos = magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
    link_type, = struct.unpack_from(endian + "I", blob, 20)
    records, streams = [], {}
    cursor = 24
    while cursor + 16 <= len(blob):
        sec, sub, captured, original = struct.unpack_from(endian + "IIII", blob, cursor)
        cursor += 16
        packet = blob[cursor:cursor + captured]
        cursor += captured
        if link_type == 1:
            ip = 14
            if len(packet) < 14 or packet[12:14] != b"\x08\x00":
                continue
        elif link_type == 113:
            ip = 16
        elif link_type == 276:
            ip = 20
        elif link_type in (101, 228):
            ip = 0
        else:
            raise AssertionError(f"Unsupported pcap datalink {link_type}")
        if len(packet) < ip + 20 or packet[ip] >> 4 != 4 or packet[ip + 9] != 6:
            continue
        ihl = (packet[ip] & 15) * 4
        total_length, = struct.unpack_from("!H", packet, ip + 2)
        tcp = ip + ihl
        src_port, dst_port, seq, ack = struct.unpack_from("!HHII", packet, tcp)
        tcp_len = (packet[tcp + 12] >> 4) * 4
        flags = packet[tcp + 13]
        payload = packet[tcp + tcp_len:ip + total_length]
        direction = "request" if dst_port == server_port else "response"
        ephemeral = src_port if direction == "request" else dst_port
        record = {"number": len(records) + 1, "timestamp": sec + sub / (1e9 if nanos else 1e6),
                  "src": socket.inet_ntoa(packet[ip + 12:ip + 16]), "src_port": src_port,
                  "dst": socket.inet_ntoa(packet[ip + 16:ip + 20]), "dst_port": dst_port,
                  "seq": seq, "ack": ack, "flags_hex": f"0x{flags:02x}",
                  "flags": "".join(label for bit, label in ((2, "S"), (16, "A"), (8, "P"), (1, "F"), (4, "R")) if flags & bit),
                  "payload_length": len(payload), "captured_length": captured,
                  "original_length": original}
        records.append(record)
        if payload:
            streams.setdefault((ephemeral, direction), {})[seq] = payload
    decoded = []
    for (ephemeral, direction), segments in sorted(streams.items()):
        ordered = sorted(segments.items())
        data, next_seq = b"", ordered[0][0]
        for seq, payload in ordered:
            assert seq <= next_seq, f"TCP reassembly gap at {seq}, expected {next_seq}"
            trim = max(0, next_seq - seq)
            data += payload[trim:]
            next_seq = max(next_seq, seq + len(payload))
        offset, frames = 0, []
        while offset + 4 <= len(data):
            length, = struct.unpack_from("!I", data, offset)
            assert 1 <= length <= 4096 and offset + 4 + length <= len(data), "bad application frame in capture"
            text = data[offset + 4:offset + 4 + length].decode("utf-8")
            frames.append({"payload_length": length, "header_hex": data[offset:offset + 4].hex(" "), "text": text})
            offset += 4 + length
        assert offset == len(data), "trailing incomplete captured application frame"
        decoded.append({"ephemeral_port": ephemeral, "direction": direction, "frames": frames})
    assert records, "no TCP packets"
    requests = [f["text"] for s in decoded if s["direction"] == "request" for f in s["frames"]]
    responses = [f["text"] for s in decoded if s["direction"] == "response" for f in s["frames"]]
    assert {"SYSINFO", "PING", "ECHO packet-capture-demo", "SLEEP 50"}.issubset(set(requests)), requests
    assert len(responses) >= 4 and all(x.startswith("OK") for x in responses), responses
    return {"link_type": link_type, "packet_count": len(records), "pcap_bytes": len(blob),
            "syn_packets": sum("S" in x["flags"] for x in records),
            "fin_packets": sum("F" in x["flags"] for x in records),
            "rst_packets": sum("R" in x["flags"] for x in records),
            "data_packets": sum(x["payload_length"] > 0 for x in records),
            "connections": len(set(s["ephemeral_port"] for s in decoded)),
            "decoded_streams": decoded, "packets": records}


def packet_capture():
    pcap = EVIDENCE / "loopback.pcap"
    cap_log_path = RAW / "tcpdump_capture.log"
    with Server("capture", 19090, timeout_ms=2000) as server:
        with cap_log_path.open("w") as cap_log:
            cap = subprocess.Popen(["tcpdump", "-i", "lo", "-nn", "-s", "0", "-U", "-w", str(pcap),
                                    "tcp", "port", "19090"], stdout=cap_log, stderr=cap_log)
            try:
                assert wait_for(lambda: "listening on" in cap_log_path.read_text() or cap.poll() is not None, 5)
                assert cap.poll() is None, cap_log_path.read_text()
                transcript = []
                for command, args in (("SYSINFO", []), ("PING", []),
                                      ("ECHO", ["packet-capture-demo"]), ("SLEEP", ["50"])):
                    result = client(server.port, command, *args)
                    transcript.append(f"$ client --port 19090 {command} {' '.join(args)}\n{result.stdout}")
                save("capture_commands.txt", "\n".join(transcript))
                # Allow libpcap's kernel capture buffer to be dispatched before SIGINT.
                time.sleep(1.2)
            finally:
                if cap.poll() is None:
                    cap.send_signal(signal.SIGINT)
                cap.wait(timeout=5)
    assert cap.returncode == 0, cap_log_path.read_text()
    summary = run(["tcpdump", "-nn", "-tttt", "-r", pcap])
    hex_dump = run(["tcpdump", "-nn", "-X", "-r", pcap])
    save("tcpdump_summary.txt", "$ tcpdump -nn -tttt -r evidence/loopback.pcap\n" + summary.stdout + summary.stderr)
    save("tcpdump_hex.txt", "$ tcpdump -nn -X -r evidence/loopback.pcap\n" + hex_dump.stdout + hex_dump.stderr)
    analysis = parse_pcap(pcap, server.port)
    (EVIDENCE / "packet_analysis.json").write_text(json.dumps(analysis, indent=2) + "\n")
    RESULTS["packet_capture"] = {k: v for k, v in analysis.items() if k not in ("packets", "decoded_streams")}
    frames = []
    for stream in analysis["decoded_streams"]:
        frames.append(f"TCP ephemeral port {stream['ephemeral_port']} {stream['direction']}")
        for frame in stream["frames"]:
            frames.append(f"length={frame['payload_length']} header={frame['header_hex']}\n{frame['text']}\n")
    save("decoded_frames.txt", "\n".join(frames))
    return RESULTS["packet_capture"]


def cleanup():
    for server in SERVERS:
        try:
            server.stop()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="Use already-built debug and release binaries")
    parser.add_argument("--skip-capture", action="store_true", help="Development only; final submission requires capture")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    RESULTS["started_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    RESULTS["capture_skipped"] = args.skip_capture
    try:
        test("Linux environment and required tools", environment)
        if not args.skip_build:
            test("Build debug and release", build)
        test("Normal features and abnormal conditions", normal_and_exceptional)
        test("Twelve simultaneous C clients and fork children", concurrency)
        test("Robustness comparison fragmented header", fragmented_comparison)
        test("Robustness comparison idle timeout", idle_comparison)
        test("Robustness comparison zombie reaping", zombie_comparison)
        test("Bounded admission control", admission_limit)
        test("Compile time and runtime debug matrix", debug_matrix)
        test("Dynamic shared library linkage", shared_library)
        if not args.skip_capture:
            test("Real loopback tcpdump capture and frame analysis", packet_capture)
    finally:
        cleanup()
        RESULTS["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_results()
    print(f"{RESULTS['pass_count']}/{RESULTS['test_count']} passed; evidence: {EVIDENCE}")
    return 0 if RESULTS["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
