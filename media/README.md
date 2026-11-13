# ForkSysInfo 影片與執行畫面

公開專案：[mimimaomao1117/forksysinfo](https://github.com/mimimaomao1117/forksysinfo)。文件更新日期為 2026 年 11 月 13 日。

[兩分鐘 MP4](ForkSysInfo_2min.mp4) 為 120 秒的繁體中文旁白實測證據解說，附[字幕](ForkSysInfo_2min.zh-TW.srt)與[旁白逐字稿](ForkSysInfo_2min_transcript.txt)。影片末段的 START_DEMO.cmd 屬於桌面完整套件；GitHub 下載版請依[專案 README](../README.md)使用原生 Linux 或 Docker。

`00_summary.png` 至 `05_packets.png` 是原始實測 log 檢視器的畫面擷取，可與 `evidence/` 內的 JSON、log 及 PCAP 核對。`06_live_console.png` 是安裝後 Linux 6.12.117 環境直接執行 C 程式的虛擬機終端畫面。第一次參考實測使用 Linux 6.12.51；兩組環境的證據分別保存在 `evidence/` 與 `evidence-recheck/`。

本次文件更新補充公開下載與重現方式，錄製影片、字幕、原始截圖及原始實測紀錄均保留原有內容。完整技術說明見[PDF 報告](../report/ForkSysInfo_Report.pdf)及[報告文字版](../docs/REPORT.md)。
