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

The [two-minute English video](ForkSysInfo_2min.mp4) uses the current console screenshots and both diagrams. Its narration, [English SRT subtitles](ForkSysInfo_2min.en.srt), and [transcript](ForkSysInfo_2min_transcript.txt) follow the revised report. This is a narrated walkthrough of the recorded command-line evidence; the screenshots show the actual runs rather than a newly recorded live session.

The video covers the fork-based design, length-prefixed messages, SYSINFO, twelve simultaneous `SLEEP 3000` requests completed in 3.175 seconds, the three robustness comparisons, both debug controls, dynamic linking, TShark analysis, and the 11/11 integration result. Packet figures refer to `evidence-cli/loopback.pcap`: four TCP connections and forty packets.

The older `00_summary.png` through `06_live_console.png` remain reference images from earlier runs. They are separate from the current `cli/` screenshots and English video.

The Windows launchers require the complete desktop bundle. A plain GitHub clone does not include `portable-linux/`; use the Linux or Docker instructions in the [project README](../README.md).

## Video build sources

The [timeline](video_timeline.json) contains the English narration and cue timings. The [manifest](video_manifest.json) records the exact source-image hashes, displayed crops, audio timings, and MP4 properties. The video is 1920 by 1080 at 25 fps, with English narration and captions throughout.

The included narration uses the Windows English voice Microsoft Zira Desktop. To rebuild on Windows, install Python with Pillow and FFmpeg, then run from the project root:

```powershell
powershell -File scripts/narrate_video.ps1 -WorkDirectory work/video
python scripts/build_video.py --work work/video
```

FFmpeg and ffprobe must be on PATH; their locations can also be supplied with `--ffmpeg` and `--ffprobe`. Intermediate WAV and frame files belong in the local work directory, outside the submitted media directory.
