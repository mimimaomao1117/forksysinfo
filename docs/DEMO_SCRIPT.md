# ForkSysInfo 兩分鐘證據講解腳本

影片型式為有旁白的實際執行證據講解，畫面引用本專案的真實測試輸出、行程快照及封包分析。執行截圖是原始 log 檢視器的畫面擷取；影片並非未剪輯的全程桌面錄影。完整原始 log 與 pcap 隨專案保留，現場可重新執行。以下數字對應 2026 年 11 月 13 日的參考實測，整合驗證共 11 項，全部通過。

| 時間 | 畫面內容 | 繁體中文字幕 |
|---|---|---|
| 00:00–00:15 | 專案標題與 Linux 環境資訊 | 本專案以 C 語言實作 TCP 系統資訊服務，透過 fork 為每條連線建立子行程，全程不使用執行緒。十一項整合驗證全部通過。 |
| 00:15–00:30 | 架構與 `.so` 動態連結證據 | 用戶端與伺服器共同載入 libnetsys.so，封包格式為四個位元組的長度加上文字內容。 |
| 00:30–00:45 | SYSINFO 真實回應 | 用戶端要求 SYSINFO，伺服器回傳 Linux 系統資訊與處理這條連線的子行程 PID。 |
| 00:45–01:05 | 12 個子行程同時存在的快照與成功結果 | 十二個用戶端各等待兩秒，總耗時僅 2.141 秒，快照同時顯示十二個子行程。循序等待的理論下限是二十四秒。 |
| 01:05–01:25 | 三組 robustness 實測比較 | 分段 PING 正常模式成功，比較模式出現 Broken pipe；閒置連線剩餘子行程為零比一；zombie 數量也是零比一。 |
| 01:25–01:40 | debug 四格結果 | 四種組合的 debug 行數為零、八、零、零。編譯期與執行期都開啟時才有 debug。 |
| 01:40–01:55 | tcpdump 封包與應用層 payload | pcap 包含四條連線、四十個封包，沒有 RST。PING 的長度前綴是零、零、零、四。 |
| 01:55–02:00 | 重現指令 | 執行 START_DEMO.cmd 即可重新驗證，並可進入 Linux 終端機現場展示。 |

## English narration

The following segments correspond to the same timeline. Leave a short pause between segments and keep the complete video at two minutes.

1. This C project provides a TCP system information service. The server forks one child for each connection and uses no threads. All eleven integration checks passed in Linux on this computer.
2. Both the client and the server dynamically load the same shared library. Each application message contains a four byte network order length, followed by the text payload.
3. Here is a real system information request. The response contains Linux system details and the process identifier of the child handling this connection.
4. Twelve C clients each request a two second sleep. Twelve server children exist simultaneously, and every client succeeds. The total time is two point one four one seconds. Sequential waiting alone would require at least twenty four seconds.
5. Three paired tests expose the differences. A fragmented PING succeeds normally but fails in demonstration mode. After an idle deadline, child counts are zero versus one. Zombie counts are also zero versus one.
6. Debug requires both compile time and runtime support. The four combinations produce zero, eight, zero, and zero debug lines. Runtime flags cannot restore debug code removed during compilation.
7. Tcpdump records four loopback connections and forty packets, with no resets. We inspect the handshake, request, response, and shutdown. The PING length prefix equals four.
8. Run START DEMO to reproduce the tests on this computer.

## 現場手動展示提示

先在第一個終端機開啟 server，在第二個終端機執行 SYSINFO、PING 與 ECHO。接著執行完整測試，展示當次產生的併發快照及三組比較。最後用 `tcpdump -nn -X -r evidence/loopback.pcap` 或 Wireshark 開啟原始封包，指出長度前綴與命令。

Windows 可執行根目錄的 `START_DEMO.cmd` 自動驗證；`LINUX_SHELL.cmd` 會進入 Linux 並自動切換至 `/root/ForkSysInfo`。現場重跑的 PID 與耗時會變動，應以當次產生的結果為準。
