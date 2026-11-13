#!/usr/bin/env python3
"""Run short, genuine Linux command-line demonstrations for report screenshots.

The normal integration suite remains in tests/run_tests.py. This script keeps
its extra output in evidence-cli/ without replacing the suite's results.json.
"""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import shlex
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence-cli"
RAW = EVIDENCE / "raw"


class Tee:
    def __init__(self, console, output):
        self.console = console
        self.output = output

    def write(self, text):
        self.console.write(text)
        self.output.write(text)
        self.flush()
        return len(text)

    def flush(self):
        self.console.flush()
        self.output.flush()


def command(args, timeout=90):
    args = [str(arg) for arg in args]
    displayed = args[2] if len(args) == 3 and args[:2] == ["sh", "-c"] else shlex.join(args)
    print(("# " if os.geteuid() == 0 else "$ ") + displayed, flush=True)
    result = subprocess.run(args, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=timeout)
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.returncode:
        raise RuntimeError(f"command exited {result.returncode}")
    return result.stdout


def helpers():
    spec = importlib.util.spec_from_file_location("forksysinfo_tests", ROOT / "tests/run_tests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.EVIDENCE = EVIDENCE
    module.RAW = RAW
    return module


def build(tests):
    command(["uname", "-srmo"])
    for enabled in (1, 0):
        command(["make", "-B", f"DEBUG={enabled}", "all"])
    return {"debug_build": True, "release_build": True}


def sysinfo(tests):
    with tests.Server("cli_sysinfo", 19200, timeout_ms=2000) as server:
        print("server: " + shlex.join([str(x.relative_to(ROOT)) if isinstance(x, Path) else str(x)
                                       for x in server.args]))
        print(f"server parent PID={server.pid}")
        outputs = []
        for request in (("SYSINFO",), ("PING",), ("ECHO", "hello from the command line")):
            args = ["./build/debug/client", "--port", str(server.port), *request]
            outputs.append(command(args))
        assert outputs[0].startswith("OK SYSINFO")
        assert outputs[1].startswith("OK PONG")
        assert outputs[2].startswith("OK hello")
    return {"parent_pid": server.pid, "responses": outputs}


def concurrency(tests):
    procs = []
    with tests.Server("cli_concurrency", 19210, timeout_ms=5000) as server:
        print(f"server parent PID={server.pid}; client count=12; SLEEP=3000 ms")
        print("client command (12 subprocesses): ./build/debug/client --port 19210 SLEEP 3000")
        begin = time.monotonic()
        try:
            for _ in range(12):
                procs.append(subprocess.Popen(
                    [str(ROOT / "build/debug/client"), "--port", str(server.port),
                     "SLEEP", "3000"], cwd=ROOT, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            observed = tests.wait_for(
                lambda: [x for x in tests.children(server.pid) if x["state"] != "Z"]
                if len([x for x in tests.children(server.pid) if x["state"] != "Z"]) == 12
                else False, timeout=2)
            assert observed and len(observed) == 12, "12 overlapping workers not observed"
            processes = command(["ps", "-o", "pid,ppid,stat,comm", "--ppid", str(server.pid)])
            (RAW / "cli_concurrency_ps.txt").write_text(processes, encoding="utf-8")
            sockets = tests.run(["ss", "-tnp"]).stdout
            (RAW / "cli_concurrency_ss.txt").write_text(sockets, encoding="utf-8")
            replies = []
            print("client responses:")
            for index, proc in enumerate(procs, 1):
                stdout, stderr = proc.communicate(timeout=10)
                assert proc.returncode == 0 and stdout.startswith("OK SLEPT 3000"), (stdout, stderr)
                print(f"{index:02d}  {stdout.strip()}")
                replies.append({"client": index, "pid": proc.pid,
                                "response": stdout.strip(), "exit_code": proc.returncode})
            elapsed = round(time.monotonic() - begin, 3)
            print(f"observed {len(observed)} workers at one time; elapsed={elapsed:.3f} s")
            print("serial SLEEP lower bound: 12 x 3 = 36 s")
            assert elapsed < 12, f"unexpected elapsed time: {elapsed}"
            return {"parent_pid": server.pid, "simultaneous_children": observed,
                    "simultaneous_child_count": len(observed), "elapsed_seconds": elapsed,
                    "sleep_ms": 3000, "serial_lower_bound_seconds": 36, "clients": replies}
        finally:
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()


def robustness(tests):
    rows = {"fragmented_header": [], "idle_timeout": [], "zombie_reaping": []}
    print("fragmented PING frame: send 1 byte, then 2 bytes, then 5 bytes")
    for offset, unsafe in enumerate((False, True)):
        mode = "unsafe" if unsafe else "robust"
        with tests.Server(f"cli_fragment_{mode}", 19220 + offset, unsafe=unsafe) as server:
            with server.connect() as sock:
                packet = struct.pack("!I", 4) + b"PING"
                sock.sendall(packet[:1])
                time.sleep(0.15)
                try:
                    sock.sendall(packet[1:3])
                    time.sleep(0.1)
                    sock.sendall(packet[3:])
                    response = tests.recv_frame(sock)
                except (OSError, EOFError) as exc:
                    response = f"{type(exc).__name__}: {exc}"
                assert response.startswith("OK PONG") == (not unsafe)
                print(f"  {mode:6s}: {response}")
                rows["fragmented_header"].append({"mode": mode, "response": response})
    print()
    print("idle connection: send no bytes; timeout=500 ms; inspect after 1.2 s")
    for offset, unsafe in enumerate((False, True)):
        mode = "unsafe" if unsafe else "robust"
        with tests.Server(f"cli_idle_{mode}", 19222 + offset,
                          timeout_ms=500, unsafe=unsafe) as server:
            with server.connect():
                assert tests.wait_for(lambda: tests.children(server.pid), 1)
                time.sleep(1.2)
                observed = tests.children(server.pid)
                active = [x for x in observed if x["state"] != "Z"]
                assert len(active) == (1 if unsafe else 0)
                print(f"  {mode:6s}: active workers={len(active)}; children={[(x['pid'], x['state']) for x in observed]}")
                rows["idle_timeout"].append({"mode": mode, "active_workers": len(active),
                                             "children": observed, "timeout_ms": 500})
    print()
    print("completed PING client: inspect child state after 300 ms")
    for offset, unsafe in enumerate((False, True)):
        mode = "unsafe" if unsafe else "robust"
        with tests.Server(f"cli_zombie_{mode}", 19224 + offset, unsafe=unsafe) as server:
            result = tests.client(server.port, "PING")
            assert result.stdout.startswith("OK PONG")
            time.sleep(0.3)
            observed = tests.children(server.pid)
            zombies = [x for x in observed if x["state"] == "Z"]
            assert len(zombies) == (1 if unsafe else 0)
            print(f"  {mode:6s}: zombies={len(zombies)}; children={[(x['pid'], x['state']) for x in observed]}")
            rows["zombie_reaping"].append({"mode": mode, "zombies": len(zombies),
                                           "children": observed, "response": result.stdout.strip()})
    print("All temporary server processes have been stopped.")
    return rows


def debug_library(tests):
    matrix = []
    print("compile DEBUG / runtime --debug / observed DEBUG log lines")
    for index, (variant, enabled) in enumerate((("debug", False), ("debug", True),
                                               ("release", False), ("release", True))):
        with tests.Server(f"cli_debug_{variant}_{int(enabled)}", 19240 + index,
                          variant=variant, debug=enabled) as server:
            result = tests.client(server.port, "PING", variant=variant, debug=enabled)
            assert result.stdout.startswith("OK PONG")
        text = server.path.read_text(encoding="utf-8") + result.stderr
        lines = [line for line in text.splitlines() if "DEBUG " in line]
        compile_enabled = int(variant == "debug")
        assert bool(lines) == (compile_enabled and enabled)
        print(f"  {compile_enabled}             {str(enabled):5s}             {len(lines)}")
        matrix.append({"compile_debug": compile_enabled, "runtime_debug": enabled,
                       "debug_line_count": len(lines)})
        (RAW / f"cli_debug_{variant}_{int(enabled)}_combined.txt").write_text(text, encoding="utf-8")
    print()
    for binary in ("server", "client"):
        command(["sh", "-c", f"ldd build/debug/{binary} | grep libnetsys"])
    command(["sh", "-c", "readelf -d build/debug/server | grep -E 'NEEDED.*libnetsys|RUNPATH'"])
    return {"debug_matrix": matrix}


def packet_hex(tests):
    path = EVIDENCE / "loopback.pcap"
    if not path.exists():
        raise FileNotFoundError("Run the packet capture suite before packet-hex")
    output = command(["tcpdump", "-nn", "-X", "-r", "evidence-cli/loopback.pcap", "-c", "1",
                      "tcp[((tcp[12] & 0xf0) >> 2):4] = 4"])
    assert "PING" in output, "PING bytes were not displayed"
    return {"pcap": "evidence-cli/loopback.pcap", "displayed_request": "PING"}


def tshark(tests):
    path = EVIDENCE / "loopback.pcap"
    if not path.exists():
        raise FileNotFoundError("Run the packet capture suite before tshark")
    version = command(["sh", "-c", "tshark --version | head -n1"])
    fields = ["frame.number", "tcp.srcport", "tcp.dstport", "tcp.flags",
              "tcp.seq", "tcp.ack", "tcp.len"]
    args = ["tshark", "-r", "evidence-cli/loopback.pcap", "-Y", "tcp.stream == 0",
            "-T", "fields", "-E", "header=y"]
    for field in fields:
        args += ["-e", field]
    align = 'awk \'{printf "%-13s %-12s %-12s %-11s %-9s %-9s %s\\n", $1, $2, $3, $4, $5, $6, $7}\''
    output = command(["sh", "-c", shlex.join(args) + " | " + align])
    assert "frame.number" in output and "19090" in output, "TCP stream table missing"
    return {"pcap": "evidence-cli/loopback.pcap", "stream": 0,
            "version_output": version, "table_output": output}


def tshark_hex(tests):
    path = EVIDENCE / "loopback.pcap"
    if not path.exists():
        raise FileNotFoundError("Run the packet capture suite before tshark-hex")
    display_filter = "tcp.len == 8 && tcp.dstport == 19090"
    command(["tshark", "-r", "evidence-cli/loopback.pcap", "-Y", display_filter, "-x"])
    output = command(["tshark", "-r", "evidence-cli/loopback.pcap", "-Y", display_filter,
                      "-T", "fields", "-e", "tcp.payload"])
    assert "0000000450494e47" in output.replace(":", "").lower(), "PING payload missing"
    return {"pcap": "evidence-cli/loopback.pcap", "display_filter": display_filter,
            "payload_hex": "0000000450494e47"}


def summary(tests):
    path = EVIDENCE / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    print("Saved integration run: evidence-cli/results.json")
    print(f"Saved complete run: {data.get('started_utc', 'time not recorded')}")
    for row in data["tests"]:
        print(("PASS " if row["passed"] else "FAIL ") + row["name"])
    print(f"{data['pass_count']}/{data['test_count']} test groups passed")
    print("Full stdout and per-test logs are retained in evidence-cli/.")
    return {"reference_file": str(path.relative_to(ROOT)), "pass_count": data["pass_count"],
            "test_count": data["test_count"]}


def suite(tests):
    original_args = sys.argv
    try:
        sys.argv = [str(ROOT / "tests/run_tests.py")]
        result = tests.main()
        if result:
            raise RuntimeError("integration suite failed; inspect evidence-cli/results.json")
        return {"pass_count": tests.RESULTS["pass_count"],
                "test_count": tests.RESULTS["test_count"],
                "results": "evidence-cli/results.json"}
    finally:
        sys.argv = original_args


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "sysinfo", "concurrency", "robustness",
                                         "debug-library", "packet-hex", "tshark",
                                         "tshark-hex", "summary", "suite"))
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    tests = helpers()
    original_stdout = sys.stdout
    log_path = RAW / f"console_{args.mode}.txt"
    try:
        with log_path.open("w", encoding="utf-8") as log:
            sys.stdout = Tee(original_stdout, log)
            print("UTC " + datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
            print(("# " if os.geteuid() == 0 else "$ ") + "python3 scripts/cli_evidence.py " + args.mode)
            function = {"build": build, "sysinfo": sysinfo, "concurrency": concurrency,
                        "robustness": robustness, "debug-library": debug_library,
                        "packet-hex": packet_hex, "tshark": tshark,
                        "tshark-hex": tshark_hex, "summary": summary, "suite": suite}[args.mode]
            result = function(tests)
        results_path = EVIDENCE / "console_results.json"
        results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}
        results[args.mode] = {"recorded_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                              "passed": True, "detail": result, "transcript": str(log_path.relative_to(ROOT))}
        results_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        return 0
    finally:
        sys.stdout = original_stdout
        tests.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
