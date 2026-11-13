# Figures and recordings

Public project: [mimimaomao1117/forksysinfo](https://github.com/mimimaomao1117/forksysinfo).

The [English PDF report](../report/ForkSysInfo_Report.pdf) uses the current [native command-line screenshots](cli/):

| File | Recorded command-line output |
|---|---|
| `cli/01_build.png` | Debug and release builds |
| `cli/02_sysinfo.png` | Live SYSINFO, PING and ECHO requests |
| `cli/03_concurrency.png` | Twelve worker processes and twelve C client responses |
| `cli/04_robustness.png` | Fragmented request, idle timeout and zombie comparisons |
| `cli/05_debug_library.png` | Debug controls, ldd and ELF RUNPATH |
| `cli/06_tshark.png` | TShark version and the first TCP stream |
| `cli/07_packets_hex.png` | Packet hex and the PING payload |
| `cli/08_tests.png` | Complete integration test run |

These PNGs were captured directly from the QEMU Linux framebuffer. The full, uncropped files are retained here; the PDF omits unused blank space below some output. Raw transcripts and measurements are in `../evidence-cli/`.

The architecture and framing diagrams are available as editable SVG and rendered PNG files in [diagrams/](diagrams/): `architecture.svg`, `architecture.png`, `protocol.svg`, and `protocol.png`.

The older `00_summary.png` through `06_live_console.png` and the [120-second video](ForkSysInfo_2min.mp4) remain as reference material from the earlier runs. The video retains its original Traditional Chinese narration, [SRT subtitles](ForkSysInfo_2min.zh-TW.srt), and [transcript](ForkSysInfo_2min_transcript.txt). The revised report is in English.

The video's Windows launcher belongs to the complete desktop bundle. A plain GitHub clone does not include `portable-linux/`; use the Linux or Docker instructions in the [project README](../README.md).
