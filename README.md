# ForkSysInfo C 語言行程式 TCP 用戶端與伺服器

GitHub 版本收錄完整 C 原始碼、測試、報告 PDF、120 秒影片、執行畫面及原始封包證據。大型 `portable-linux/` 離線環境與建置產物不納入 Git；從 GitHub 下載後，請依下方原生 Linux 或 Docker 步驟執行。Windows 的三個 `.cmd` 入口需要桌面完整套件中的 `portable-linux/` 才能使用。

本專案提供以 `fork()` 為每條連線建立子行程的 TCP 伺服器、C 語言用戶端，以及雙方共同動態連結的 `libnetsys.so`。功能包含系統資訊查詢、連線檢查、字串回傳及延遲工作。`--unsafe` 是課堂比較用的模式，會關閉三項健全性機制，以便在相同程式中重現差異。

程式必須在 Linux 執行。Windows 上可使用可攜式 QEMU Linux 虛擬機，或已能啟動 Linux backend 的 Docker Desktop；MinGW 的 Windows 執行環境無法直接提供本作業要求的 `fork()` 與 Linux `.so`。SYSINFO 回傳的是 Linux 執行環境所見的系統資訊。

## 本次驗證環境

本機的 Docker backend 受硬體虛擬化可用性限制，因此本次使用 QEMU 軟體模擬的 Linux 環境執行實測。核心為 `6.12.51-0-virt`，GCC 14.2.0，GNU Make 4.4.1，Python 3.12.16，tcpdump 4.99.5。Docker 指令是另一種重現途徑，不能視為本次已成功執行 Docker 的證據。

本次 11 項整合驗證全部通過。12 個 C client 的 SLEEP 2000 請求同時對應 12 個子行程，總耗時 2.141 秒；若依序等待，僅 SLEEP 就需 24 秒。封包擷取保留 4 條 TCP 連線、40 個封包與 8 個資料封包。三組健全性比較及 debug 四種組合均有原始 log。

## Windows 可攜式 Linux 啟動

將整個專案資料夾保留在同一處，不要單獨移動啟動檔或 `portable-linux/`。

1. 雙擊根目錄的 `START_DEMO.cmd`，啟動隨附 QEMU Linux 環境並執行完整測試。
2. 等待畫面顯示測試結果，再檢查 `runs/時間戳記/` 中新產生的 JSON、log 與 pcap。`evidence/` 保留報告所引用的第一次實測。
3. 要手動操作 Linux，執行根目錄的 `LINUX_SHELL.cmd`。它會自動切換到 `/root/ForkSysInfo`，可直接使用本文件的 server 與 client 指令。可同時開啟兩個視窗。
4. 完成後執行 `STOP_LINUX.cmd`，正常關閉背景 Linux 虛擬機。

`START_DEMO.cmd` 會先把 Windows 資料夾中的原始碼更新到 Linux 環境，再測試。此方式使用軟體模擬，不依賴 Docker backend，也不需要為本作業修改 BIOS 的硬體虛擬化設定。首次開機仍需要等待 Linux 啟動；影片及報告中的 PID 是本次實測值，重新執行時會改變。

隨附磁碟安裝後的 Linux 核心為 `6.12.117-0-virt`，也已再次通過全部測試，結果另存於 `evidence-recheck/`。啟動時不需要下載套件；請預留約 2 GB 記憶體與 1 至 3 分鐘開機時間。

## Linux 快速執行

Ubuntu 或 Debian 安裝工具：

```bash
sudo apt-get update
sudo apt-get install -y build-essential python3 tcpdump iproute2 binutils
make DEBUG=1
```

在第一個終端機啟動伺服器：

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

按 `Ctrl+C` 關閉伺服器。程式會清理子行程。預設綁定 loopback，其他電腦不會直接連入。

## Windows Docker 快速執行

先啟動 Docker Desktop，確認使用 Linux containers。用 PowerShell 切換到本資料夾：

```powershell
docker build -t forksysinfo .
docker run --rm --cap-add NET_RAW --cap-add NET_ADMIN -v "${PWD}:/project" forksysinfo bash scripts/run_all.sh
```

這會在自己的電腦內以 Linux 執行，並將重新產生的測試證據寫回本資料夾。抓取 loopback 封包所需的 capability 只加給此次容器。正式用戶端與伺服器不需要這些 capability。

若要手動展示，請保持容器開啟：

```powershell
docker run --rm -it --name forksysinfo-demo --cap-add NET_RAW --cap-add NET_ADMIN -v "${PWD}:/project" forksysinfo bash
```

在容器終端機內執行 `make DEBUG=1` 及伺服器。再從另一個 PowerShell 終端機進入同一個容器：

```powershell
docker exec -it forksysinfo-demo bash
```

此時可執行前述 client 指令。同一個容器中的 `127.0.0.1` 才是本專案伺服器使用的 loopback。

## 全部驗證

```bash
bash scripts/run_all.sh
```

需要有權限執行 `tcpdump`；Docker 方式已設定 capability。測試涵蓋至少 12 個同時連線的 C client、三組健全性比較、協定與異常輸入、debug 控制及動態連結。真實結果、行程快照與原始封包存於 `evidence/`。請保留原始 `.pcap`，可用 Wireshark 開啟。

測試時會短暫使用指定的測試埠號；若測試失敗，先讀取 `evidence/` 中的 log，確認埠號未被其他程式占用。

## 編譯與執行時 debug

```bash
make DEBUG=1
./build/debug/server --debug

make DEBUG=0
./build/release/server --debug
```

編譯時 `DEBUG=1` 才保留 debug 程式碼；執行時還要指定 `--debug` 才會輸出。`DEBUG=0` 即使加上 `--debug`，也不會重新開啟已被編譯移除的 debug 訊息。一般錯誤與生命週期 log 仍保留。debug 與 release 存於不同目錄，避免舊物件檔混用。

## 共享函式庫

```bash
ldd build/debug/server
ldd build/debug/client
readelf -d build/debug/server
readelf -d build/debug/client
```

雙方都需要 `libnetsys.so`。執行檔使用相對自身位置的 `$ORIGIN` 搜尋函式庫，所以應保留相同 build 目錄中的檔案，不要只複製單獨的執行檔。

## 健全性比較模式

```bash
./build/debug/server --port 9090 --timeout-ms 1000
./build/debug/server --port 9091 --timeout-ms 1000 --unsafe
```

`--unsafe` 關閉完整讀取迴圈、接收逾時與執行中的子行程回收，分別用來觀察分段資料失敗、閒置連線占住子行程與 zombie 累積。固定緩衝區界限仍保留，避免將作業示範變成記憶體破壞程式。完整比較由測試自動執行並清理。

## 繳交內容與現場展示

* `src/`、`include/`、`Makefile`：完整 C 原始碼與建置規則。
* `tests/`、`scripts/`：可重新執行的驗證與展示工具。
* `evidence/`：測試結果、真實 log、行程快照與 loopback pcap。
* `docs/REPORT.md`：系統設計與技術報告文字版。
* `docs/DEMO_SCRIPT.md`：兩分鐘影片與現場展示的講稿。
* 報告、截圖及影片：請見本專案隨附的對應檔案。執行截圖是實際原始 log 檢視器的畫面擷取；影片是有旁白的證據講解，並非未剪輯的全程桌面錄影。

上課前請在自己的電腦重新執行一次測試，確認選用的 Linux 虛擬機已可啟動；若使用 Docker，請先建立映像檔。現場依序展示 SYSINFO、12 個同時連線、三組健全性差異及 pcap，不需要連上其他電腦。

本專案以教學為目的，未加入 TLS、使用者認證或網際網路部署防護。維持預設 loopback 即可完成作業要求。
