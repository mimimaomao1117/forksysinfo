# ForkSysInfo 系統設計與執行驗證報告

本專案以 C 語言實作 TCP 用戶端與伺服器。伺服器透過 `fork()` 為每條連線建立獨立子行程，不使用執行緒。雙方動態連結共同的 `libnetsys.so`，並提供編譯時及執行時兩層 debug 控制。系統資訊查詢是主要功能，另外提供 PING、ECHO、SLEEP 與 QUIT，以利驗證協定、併發和連線生命週期。

本次執行平台為 Windows 本機上由 QEMU 軟體模擬的 Linux 環境；Docker 與原生 Linux 是可選的重現方式。SYSINFO 顯示 Linux 環境所見的核心、主機名稱及記憶體等資訊，不代表 Windows 工作管理員的數值。

2026 年 11 月 13 日 11 時 50 分 56 秒至 11 時 51 分 05 秒（UTC+8）的 11 項整合驗證全部通過。環境紀錄為 Linux `6.12.51-0-virt`、GCC 14.2.0、GNU Make 4.4.1、Python 3.12.16 與 tcpdump 4.99.5。原始 log 採 UTC 時間，故對應 03:50:56 至 03:51:05；兩者為同一次實測。

## 1 系統架構

父行程建立 TCP listening socket，執行 `bind()`、`listen()`，接著在接收迴圈中 `accept()`。每成功接受一條連線，父行程呼叫 `fork()`。子行程關閉 listening socket，處理該連線的請求並結束；父行程關閉已交給子行程的 connected socket，立即繼續接受其他連線。雙方分別關閉不再使用的描述符，避免其他行程仍持有 socket 而延後 EOF。

```text
C client 1 ── TCP ── child process 1
C client 2 ── TCP ── child process 2
      ...                 ...
C client 12 ─ TCP ── child process 12
                         ↑ fork
                 parent listening process

client → libnetsys.so ← server
```

父行程管理子行程的數量與回收，並處理中斷或終止訊號。預設的用戶端數量上限為 64，超過上限時拒絕新增工作，避免無限制建立行程。預設綁定 `127.0.0.1`，讓展示與封包擷取都在同一台電腦完成。

伺服器子行程支援在同一條連線處理多個 frame，直到收到 QUIT、EOF 或錯誤。命令列 client 每次執行只送一個請求，收到一個回應後關閉連線。兩者的生命週期設計不同，但使用同一個 framing 協定。

`fork()` 讓各連線有獨立位址空間，單一子行程的連線錯誤不會直接結束父行程。代價是每條連線需要額外的行程資源，因此必須限制數量、設定逾時，並回收已結束的子行程。[1][2]

## 2 應用層協定

TCP 提供有序的位元組串流，不會保留應用程式每次 `send()` 的邊界。因此一次傳送可能由多次接收取得，多次傳送也可能由一次接收取得。[3] 本專案採用長度前綴，明確界定每個 frame。

| 欄位 | 大小 | 意義 |
|---|---:|---|
| payload length | 4 bytes | unsigned 32-bit，network byte order |
| payload | 1 至 4096 bytes | 文字命令或回應，不包含結尾 NUL |

例如 `PING` 的應用層資料是 `00 00 00 04 50 49 4e 47`。前 4 bytes 的數值為 4，後 4 bytes 是 ASCII 命令。程式不假設這 8 bytes 一定出現在同一個 TCP 封包中。

| 命令 | 功能 | 回應內容 |
|---|---|---|
| `SYSINFO` | 查詢伺服器所見的系統資訊 | uname、hostname、pid、uptime、RAM |
| `PING` | 確認應用程式可回應 | `OK PONG` 與子行程 PID |
| `ECHO text` | 回傳文字 | `OK` 與原始文字 |
| `SLEEP ms` | 模擬較長的工作 | 完成等待後回傳耗時設定與 PID |
| `QUIT` | 結束連線 | 結束回應 |

成功回應以 `OK` 開頭；可回覆的命令錯誤以 `ERR` 開頭。錯誤的長度、提早關閉或無法繼續解碼的 frame 會結束該連線。長度在讀取 payload 前先檢查，不依照未驗證的長度配置任意大小記憶體。

文字 payload 中的內嵌 NUL 也會被拒絕，避免 C 字串在中間結束，導致實際收到的 frame 與命令解析內容不同。SLEEP 只接受 0 到 10000 毫秒的整數。這些限制在比較模式中仍保留。

## 3 共用動態函式庫與原始碼

`include/` 宣告共同介面，`src/` 提供伺服器、用戶端及函式庫實作。共同的封包處理、數值檢查、時間與 log 功能集中在 `libnetsys.so`，避免雙方各維護一份相同程式。所有完整原始檔隨專案繳交，並可由 Makefile 重建。

| 原始檔與函式 | 主要責任 |
|---|---|
| `include/netsys.h` | 宣告協定常數、共享 API 與 `NET_DEBUG` 巨集 |
| `src/netsys.c` 的 `net_recv_frame()`、`net_send_frame()` | 接收與傳送長度前綴 frame，處理完整 I/O 與期限 |
| `src/netsys.c` 的 `net_connect()`、`net_listen()` | 建立 IPv4 連線及 listening socket |
| `src/netsys.c` 的 `net_parse_long()`、`net_log()` | 檢查數值範圍與產生帶有行程資訊的 log |
| `src/server.c` 的 `system_info()`、`handle_command()` | 取得 Linux 資訊，執行各項命令 |
| `src/server.c` 的 `serve_client()` | 子行程的持續收送迴圈與連線結束處理 |
| `src/server.c` 的 `reap_children()` | 以 `waitpid(-1, ..., WNOHANG)` 回收完成的子行程 |
| `src/server.c` 的 `main()` | 解析選項、accept、fork、限制連線數及關閉清理 |
| `src/client.c` 的 `main()` | 解析命令列、連線、發出單次請求並顯示回應 |

動態函式庫以位置獨立程式碼建置，再以 shared library 方式連結。client 與 server 的 ELF 動態資訊會列出 `libnetsys.so` 相依性；`ldd` 顯示執行時實際載入的路徑。執行檔的 RUNPATH 使用 `$ORIGIN`，讓它們在自己的目錄中找到函式庫。這使 debug 與 release 可同時存在，不需要修改全域函式庫搜尋路徑。

Makefile 將 debug 與 release 的目標分別放入 `build/debug/` 和 `build/release/`。`make DEBUG=1` 建立前者；`make DEBUG=0` 建立後者。這個設計避免切換編譯旗標時誤用先前的 `.o` 檔案。[5]

## 4 兩層 debug 控制

第一層由 Makefile 傳入編譯期旗標。關閉時，debug 巨集不產生輸出呼叫；第二層由執行期 `--debug` 決定是否輸出仍存在於程式中的 debug 訊息。編譯期關閉後，執行期旗標無法把已移除的程式碼恢復。

| 編譯設定 | 執行旗標 | 實測 debug 行數 |
|---|---|---:|
| `DEBUG=1` | 無 `--debug` | 0 |
| `DEBUG=1` | 有 `--debug` | 8 |
| `DEBUG=0` | 無 `--debug` | 0 |
| `DEBUG=0` | 有 `--debug` | 0 |

一般錯誤、啟動與重要生命週期訊息仍會保留，方便在關閉 debug 的版本診斷連線失敗。

上表統計單次 PING 交易的 client 與 server log。8 行包含連線、frame 傳送與接收、命令處理及 EOF 等 debug 記錄；不是要求所有操作固定產生 8 行。

## 5 健全性機制

正常模式使用完整接收與傳送迴圈，處理 partial I/O、`EINTR` 和提早斷線。frame 的接收以單調時鐘計算截止時間，避免對方每隔一小段時間只傳一個 byte，就無限延長資源占用。固定長度界限與命令參數檢查則限制不合法輸入。

程式抑制 `SIGPIPE` 導致的突然終止，將對方關閉後的寫入錯誤當作一般錯誤處理。父行程回收子行程，避免 zombie；連線數量有上限；伺服器結束時會清理仍存在的子行程。連線拒絕、埠號占用與系統呼叫失敗均以非零結束碼或明確 log 呈現。

socket 使用 nonblocking I/O 並搭配 `poll()` 等待 readiness。父行程的 `SIGCHLD` handler 只負責打斷等待，不在 handler 裡執行格式化輸出或修改複雜資料；回收工作在一般控制流程中完成。父行程最長每 100 毫秒重新檢查一次，避免完成的子行程長期留存。接收錯誤在可回傳時會送出 `ERR TIMEOUT`、`ERR BAD_LENGTH` 或 `ERR BAD_FRAME` 後關閉。

建立子行程時，程式暫時阻擋 SIGTERM 與 SIGINT。子行程先把終止 handler 改回預設值，再解除阻擋；父行程先記錄新 PID，再解除阻擋。這避免在 fork 前後立刻關閉伺服器時，子行程沿用父行程只設定旗標的 handler，卻仍停在接收迴圈中，造成關閉程序無法結束。

為比較效果，`--unsafe` 僅關閉下表中的三項機制。固定緩衝區與最大長度限制仍然保留，因此這個模式不是任意記憶體破壞範例，也不是正式部署模式。

| 情境 | 正常模式 | `--unsafe` 比較模式 |
|---|---|---|
| 4-byte header 被分段傳送 | 迴圈讀滿後正確解析 | 單次接收取得不足 4 bytes，請求失敗 |
| 接受連線後不傳完 frame | 到截止時間後結束子行程 | 子行程繼續等待，占用資源 |
| 用戶端完成並離開 | 父行程呼叫 `waitpid()` 回收 | 子行程留在 zombie 狀態，直到清理 |

上述差異必須看實際結果，不能只憑原始碼判斷。測試使用相同的命令、等待時間與觀察方式，分別執行正常模式及比較模式，再保存真實 log 與 `/proc` 行程狀態。[2]

三組實際執行結果如下。PID 屬於本次執行，重跑時會不同。

| 執行案例 | 正常模式實測 | 比較模式實測 |
|---|---|---|
| PING frame 分成 1、2、5 bytes 傳送 | `OK PONG pid=2114` | 連線已被關閉，測試端後續寫入出現 `BrokenPipeError` |
| 連線後不傳資料，期限設為 500 ms | 1.207 秒後觀察，PID 2118 已被回收，存活子行程 0 個 | 1.219 秒後仍有 PID 2120，狀態 S，存活子行程 1 個 |
| PING 完成並關閉 client | 子行程 PID 2123 已被回收，zombie 0 個 | PID 2126 留在 Z 狀態，zombie 1 個 |

閒置案例是在約 1.2 秒後取樣，不代表逾時設定是 1.2 秒；真正的 deadline 設定為 500 毫秒。分段案例的 1、2、5 bytes 合計包含 4-byte header 與 4-byte PING，其中第一段只有 1 byte，足以暴露單次接收的錯誤假設。測試結束時仍會清理比較模式的行程。

## 6 同時服務至少十個用戶端的證明

驗證程式同時啟動 12 個 C client，要求伺服器執行 SLEEP 工作。在所有工作尚未完成的重疊期間，擷取父子行程關係、子行程 PID 與 TCP 連線狀態，再檢查 12 個 client 均收到成功回應。

僅有 12 行成功輸出不足以證明同時服務，因為依序執行也能得到相同輸出。本次在父行程 PID 2082 下，同時觀察到 12 個子行程：2085、2087、2089、2091、2093、2094、2097、2098、2101、2103、2104、2106。它們在快照中均為 S 狀態，對應各自仍在執行的 SLEEP 工作。

12 個 C client 都收到 `OK SLEPT 2000`，結束碼均為 0，總耗時為 2.141 秒。若完全依序執行，僅等待工作本身的下限就是 12 × 2 = 24 秒。這個 24 秒是理論下限，並非另外量測出的循序版本時間。主要證據是同時存在的 12 個不同子行程與 TCP 連線，耗時是輔助證據。`ss` 在同一主機會列出每條連線的兩端，不能把 24 個 loopback endpoint 誤算為 24 個 client。

## 7 封包擷取與分析

測試使用 `tcpdump` 在 `lo` 介面擷取指定測試埠號的流量，將二進位封包保存為 `.pcap`。讀檔命令再輸出時間、來源與目的埠號、TCP flags、序號和 payload。這是同一台 Linux 主機上的 loopback 通訊，符合使用 tcpdump 的條件。[4]

```bash
tcpdump -i lo -U -w evidence/loopback.pcap 'tcp port 19090'
tcpdump -nn -tttt -r evidence/loopback.pcap
tcpdump -nn -X -r evidence/loopback.pcap
```

分析重點包括三向交握的 SYN、SYN ACK、ACK；應用層 request 與 response；長度前綴與命令文字；以及關閉時的 FIN 或異常時的 RST。TCP segment 與應用層 frame 不是一對一關係，分析 payload 時必須依序號重組同一方向的串流，並依 4-byte 長度解碼。

本次 `loopback.pcap` 為 3663 bytes，包含 4 條 TCP 連線、40 個封包，其中 8 個含應用資料、8 個帶 SYN flag、8 個帶 FIN flag，沒有 RST。SYN 計數包含 4 個 SYN 與 4 個 SYN ACK，因此代表 4 條連線。4 個請求分別為 SYSINFO、PING、ECHO 與 SLEEP 50；四個請求與四個回應共形成 8 個已解碼的應用層 frame。

以第一條連線為例，client 端為 `127.0.0.1:57382`，server 端為 `127.0.0.1:19090`。封包 1 至 3 是三向交握；封包 4 的 TCP payload 為 11 bytes，其中 4 bytes 的 `00 00 00 07` 表示後面 7 bytes 為 SYSINFO。封包 6 的 payload 為 166 bytes，由 4-byte 長度 `00 00 00 a2` 與 162-byte 回應組成。伺服器對 client 資料的 ACK 從 847142362 增加至 847142373，正好涵蓋 11 bytes；回應方向也可用相同方式檢查 166 bytes。封包 8、9、10 顯示 FIN ACK、FIN ACK 與最後 ACK 的正常關閉。

SYSINFO 回應記錄主機名稱 `localhost`、Linux release `6.12.51-0-virt`、架構 `x86_64`、子行程 PID 2150、uptime 210 秒及 RAM 資訊。另一條 PING 連線的請求 header 為 `00 00 00 04`，回應為 `OK PONG pid=2152`，與應用程式的長度前綴規格一致。

loopback 的封包時間非常接近，且可能受到核心 segmentation 或 checksum offload 的呈現方式影響。不能僅因擷取工具顯示 checksum 提示，就斷言應用程式資料毀損。原始 pcap 可用 Wireshark 開啟，以 Follow TCP Stream 交叉檢查。

## 8 執行證據與重現方式

請由專案根目錄執行 `bash scripts/run_all.sh`。它會建置兩種版本並執行驗證。`evidence/` 保存環境資訊、執行 log、結果 JSON、併發行程快照、debug 輸出以及 pcap。隨附的執行截圖是實際原始 log 檢視器的畫面擷取；兩分鐘影片是有旁白的證據講解，並非未剪輯的全程桌面錄影。

本次結果為 11 項整合驗證全部通過。其中連線上限另以 `--max-clients 2` 驗證，前兩個 child 保留時，第三個 client 收到 `ERR SERVER_BUSY`。共享函式庫檢查確認 client 與 server 都有 `DT_NEEDED libnetsys.so`，並使用 ORIGIN 相對執行檔的搜尋路徑。

| 證據檔案 | 用途 |
|---|---|
| `evidence/results.json` | 每項驗證的通過狀態、耗時與量測結果 |
| `evidence/raw/concurrency.txt` | 十二個 C client 的執行結果 |
| `evidence/raw/concurrency_processes.txt` | 重疊期間的父子行程與 PID |
| `evidence/raw/concurrency_ss.txt` | TCP established 連線快照 |
| `evidence/raw/robustness_fragmented.txt` | 分段 header 的兩種模式比較 |
| `evidence/raw/robustness_idle.txt` | 閒置連線的兩種模式比較 |
| `evidence/raw/robustness_zombies.txt` | 完成後的 zombie 行程比較 |
| `evidence/raw/debug_matrix.txt` | 編譯與執行兩層控制的四種組合 |
| `evidence/loopback.pcap` | tcpdump 取得的原始封包 |
| `evidence/raw/tcpdump_hex.txt` | 封包十六進位與文字內容 |
| `evidence/raw/decoded_frames.txt` | 依 TCP 串流解碼的應用層 frame |
| `evidence/packet_analysis.json` | 封包及串流分析的結構化結果 |

其他異常驗證包括零長度、過大與 UINT32 最大長度、內嵌 NUL、最大合法長度、同連線合併傳入 PING 與 QUIT、對方於 SLEEP 期間以 RST 斷線、埠號占用、連線被拒、錯誤命令或參數，以及較低連線上限的 admission control。每個案例均驗證可觀察的結果，並在需要時確認父行程仍可服務後續請求。

目前的證據應與同一份原始碼及建置結果一起檢視。若修改程式或在另一台電腦執行，請重新產生證據，不沿用舊 PID、舊封包或舊測試結果。

## 9 現場展示程序與限制

在自己的電腦準備好可用的 Linux 環境，先執行一次完整驗證。Windows 可使用隨附的 QEMU 方式；若 Docker 的 Linux backend 已可啟動，也可自行建置映像檔。上課依序展示一般系統資訊查詢、12 個用戶端的同時服務證據、三組健全性差異、debug 四種組合及封包分析。重新執行測試可以直接產生自己的新證據。

Windows 隨附入口為根目錄的 `START_DEMO.cmd`，用來啟動可攜式 Linux、更新主機端原始碼並執行完整驗證；`LINUX_SHELL.cmd` 用來進入可手動操作的 Linux 終端機，並自動切換至 `/root/ForkSysInfo`。可開兩個終端機，分別執行 server 與 client。新證據會存到 `runs/` 下的時間戳記資料夾，完成後使用 `STOP_LINUX.cmd` 正常關閉 Linux。請保留整個專案及 `portable-linux/` 的相對位置。

可攜式磁碟安裝後採用 Linux 6.12.117 核心，並再度通過全部 11 項測試。第二次結果保存在 `evidence-recheck/`，與本報告前述 Linux 6.12.51 的第一次封包及 PID 分開保存。`media/06_live_console.png` 是第二次環境直接執行 C 程式的虛擬機終端畫面，與原始 log 檢視器截圖一併提供。

本專案未加入 TLS 或身分驗證；預設只在 loopback 使用。每連線一個行程的設計適合本作業的十個以上連線示範，但不宣稱可無限制擴充。容器的資源資訊由其 Linux 執行環境提供，與實體 Windows 主機的視角可能不同。

## 10 參考資料

1. Linux man-pages，fork(2)：https://man7.org/linux/man-pages/man2/fork.2.html
2. Linux man-pages，wait(2) 與 waitpid(2)：https://man7.org/linux/man-pages/man2/waitpid.2.html
3. Linux man-pages，tcp(7)：https://man7.org/linux/man-pages/man7/tcp.7.html
4. The Tcpdump Group，tcpdump manual：https://www.tcpdump.org/manpages/tcpdump.1.html
5. GNU，GNU make manual：https://www.gnu.org/software/make/manual/make.html
