# ForkSysInfo C 語言 TCP 用戶端與伺服器

公開儲存庫：[mimimaomao1117/forksysinfo](https://github.com/mimimaomao1117/forksysinfo)。文件更新日期為 2026 年 11 月 13 日。

本專案以 C 語言實作 TCP 系統資訊服務。伺服器透過 `fork()` 為每條連線建立獨立子行程，不使用執行緒；client 與 server 共同動態連結 `libnetsys.so`。功能包含 SYSINFO、PING、ECHO、SLEEP 與 QUIT，並提供編譯時和執行時 debug 控制，以及三組健全性機制比較。

先查看 [PDF 報告](report/ForkSysInfo_Report.pdf)、[120 秒中文解說影片](media/ForkSysInfo_2min.mp4) 和 [原始 loopback PCAP](evidence/loopback.pcap)。[技術報告文字版](docs/REPORT.md) 與 [展示講稿](docs/DEMO_SCRIPT.md) 可直接在 GitHub 閱讀。

## 選擇執行方式

| 取得方式 | 包含內容 | 如何執行 |
|---|---|---|
| 公開 GitHub 儲存庫或原始碼 ZIP | C 原始碼、測試、文件、PDF、影片、截圖及參考封包證據 | 在原生 Linux 編譯，或使用 Docker 的 Linux 容器 |
| 桌面完整套件 | GitHub 內容，加上 Linux 建置產物、`portable-linux/` 離線環境與本機 `runs/` | Windows 雙擊 `START_DEMO.cmd`，或進入 Linux 終端機手動展示 |

`build/`、`portable-linux/` 與 `runs/` 不納入 Git。從 GitHub clone 或下載 ZIP 後，三個 Windows `.cmd` 入口需要另有完整的 `portable-linux/` 才能使用。程式的 `fork()`、`.so` 與 tcpdump 必須在 Linux 環境執行；SYSINFO 回傳該 Linux 環境所見的資訊。

## 參考實測結果

既有參考實測共 11 組整合驗證，全部通過。12 個 C client 各發出 SLEEP 2000 請求，同一快照觀察到 12 個子行程，全部成功完成，總耗時 2.141 秒。24 秒是 12 次各等待 2 秒的循序理論下限，並非另測的循序版本時間。

pcap 保留 4 條 TCP 連線、40 個封包及 8 個含應用資料的 TCP segment。三組健全性差異與 debug 四種組合均有原始 log。以下資料分開保留：

| 目錄 | 對應環境與用途 |
|---|---|
| `evidence/` | 報告引用的第一次實測，Linux `6.12.51-0-virt` |
| `evidence-recheck/` | 安裝後離線環境的第二次完整驗證，Linux `6.12.117-0-virt` |
| `runs/時間戳記/` | 桌面啟動工具每次執行匯出的新證據，僅存在於本機完整套件 |

第一次環境使用 QEMU 軟體模擬、GCC 14.2.0、GNU Make 4.4.1、Python 3.12.16 與 tcpdump 4.99.5。原本電腦的 Docker backend 未能啟動，因此下列 Docker 指令是重現方式；參考數值來自實際 QEMU Linux 執行。本次文件更新沿用這些既有證據。

## 原生 Linux 快速執行

在 Ubuntu 或 Debian 安裝工具並取得公開專案：

```bash
sudo apt-get update
sudo apt-get install -y build-essential python3 tcpdump iproute2 binutils procps git
git clone https://github.com/mimimaomao1117/forksysinfo.git
cd forksysinfo
make DEBUG=1
make DEBUG=0
```

若已下載原始碼 ZIP，先解壓縮並切換到包含 Makefile 的專案根目錄，再執行兩個 make 命令。

一般 client 與 server 可由普通使用者執行。在第一個終端機啟動 server：

```bash
./build/debug/server --host 127.0.0.1 --port 9090 --debug
```

在第二個終端機發出請求：

```bash
./build/debug/client --host 127.0.0.1 --port 9090 SYSINFO
./build/debug/client --host 127.0.0.1 --port 9090 PING
./build/debug/client --host 127.0.0.1 --port 9090 ECHO "Hello from C"
./build/debug/client --host 127.0.0.1 --port 9090 SLEEP 1000
```

伺服器預設綁定 loopback。按 `Ctrl+C` 結束時，父行程會清理工作子行程。server 支援同一條 TCP 連線處理多個 frame；命令列 client 每次執行只完成一次請求與回應。

完整驗證需要擷取封包的權限。原生 Linux 可在專案根目錄執行：

```bash
sudo bash scripts/run_all.sh
```

腳本會重新建置兩種版本、執行 11 組測試，並更新 `evidence/` 中的結果、log 與 pcap。需要保留報告引用的原始證據時，請先另存一份專案。測試會使用固定測試埠號；失敗原因可由 `results.json` 與各 server log 查看。

## Windows Docker 執行

取得公開專案後，先啟動可運作的 Docker Desktop Linux backend，再用 PowerShell 切換到專案根目錄：

```powershell
docker build -t forksysinfo .
docker run --rm --cap-add NET_RAW --cap-add NET_ADMIN -v "${PWD}:/project" forksysinfo bash scripts/run_all.sh
```

容器以 root 執行驗證，capability 供 tcpdump 擷取 loopback 流量使用，結果會寫回本機專案的 `evidence/`。一般 C client 與 server 本身不需要這些擷取權限。

要開兩個終端機手動展示，可先建立互動容器：

```powershell
docker run --rm -it --name forksysinfo-demo --cap-add NET_RAW --cap-add NET_ADMIN -v "${PWD}:/project" forksysinfo bash
```

在容器內執行 `sh scripts/demo.sh --server`；另一個 PowerShell 視窗執行 `docker exec -it forksysinfo-demo bash`，再於同一容器內執行 `sh scripts/demo.sh`。兩端必須位於同一個容器，才能共用該 Linux 主機的 `127.0.0.1`。

## Windows 桌面離線套件

此方式限包含 `portable-linux/` 的桌面完整套件。請保留專案與離線環境的相對位置，預留約 2 GB 記憶體及 1 至 3 分鐘開機時間。

1. 雙擊 `START_DEMO.cmd`。工具啟動 QEMU Linux，把本機原始碼更新至 Linux，重新建置並執行完整驗證。
2. 查看 `runs/時間戳記/` 的當次結果；報告引用的 `evidence/` 保留在本機。
3. 手動展示可開啟兩個 `LINUX_SHELL.cmd`。兩者會自動切換到 `/root/ForkSysInfo`；第一個執行 `sh scripts/demo.sh --server`，第二個執行 `sh scripts/demo.sh`。
4. 完成後執行 `STOP_LINUX.cmd`，正常關閉背景虛擬機。

離線磁碟已安裝所需工具，執行時不需下載套件，也不需修改 BIOS 的硬體虛擬化設定。PID、可用記憶體及耗時會隨每次執行而改變，應以當次證據為準。

## Debug 與共享函式庫

`make DEBUG=1` 建立 `build/debug/`，`make DEBUG=0` 建立 `build/release/`。編譯時保留 debug 程式碼，且執行時加入 `--debug`，才會輸出 debug 訊息。參考測試的四種組合如下：

| 編譯旗標 | 執行旗標 | 參考 debug 行數 |
|---|---|---:|
| `DEBUG=1` | 無 `--debug` | 0 |
| `DEBUG=1` | 有 `--debug` | 8 |
| `DEBUG=0` | 無 `--debug` | 0 |
| `DEBUG=0` | 有 `--debug` | 0 |

一般錯誤與生命週期 log 仍保留。不同版本使用不同輸出目錄，避免舊物件檔混用。兩側都動態連結 `libnetsys.so`，可檢查：

```bash
ldd build/debug/server
ldd build/debug/client
readelf -d build/debug/server
readelf -d build/debug/client
```

RUNPATH 使用 `$ORIGIN` 尋找執行檔同目錄中的 `.so`；複製執行檔時應一併保留該函式庫。

## 健全性比較與封包分析

正常模式處理 partial I/O、接收期限、錯誤輸入、斷線、連線上限及子行程回收。`--unsafe` 教學模式關閉完整接收迴圈、閒置期限及執行中的子行程回收，供相同測試比較；固定緩衝區界限仍保留。

三組參考結果為：分段 PING 正常模式成功、比較模式斷線；閒置期限後保留的子行程為 0 與 1；完成後的 zombie 數量也是 0 與 1。完整自動比較由 `scripts/run_all.sh` 執行並清理。

```bash
tcpdump -nn -tttt -r evidence/loopback.pcap
tcpdump -nn -X -r evidence/loopback.pcap
```

也可用 Wireshark 開啟 pcap。應用層 frame 使用 4-byte network-order 長度，後接 1 至 4096 bytes 文字；TCP segment 與應用 frame 不一定一對一，解讀時須依串流重組。

## 繳交與課堂展示

完整 C 原始碼位於 `src/` 與 `include/`，建置規則為 Makefile，驗證工具位於 `tests/` 與 `scripts/`。報告包含系統設計、關鍵函式、執行畫面、測試分析及完整 C 原始碼與 Makefile；影片有繁體中文旁白及字幕。

參考畫面包含原始 log 檢視器截圖與 Linux 主控台直接執行截圖。兩分鐘影片是實測證據解說；原始 log 與 PCAP 可交叉核對。現場請在自己的 Linux 環境依序展示 SYSINFO、12 個同時工作子行程、三組健全性差異及封包內容。

本專案以 loopback 教學展示為範圍，未加入 TLS 或使用者認證。
