# 🛡️ Hermes Agent 15-Day Rolling Differential Backup & Restore Table

> **最後同步時間 (Last Synced)**：`2026-11-13 03:00:55` (CST / UTC+8)
> **保留政策 (Retention)**：嚴格保留最近 **15 天** 差異備份，過期自動輪轉清理。
> **備份內容**：Hermes Core（狀態資料庫、設定檔、Skills、Memories、LINE Tunnel 守護架構）與全工作區 24H 差異異動。

---

## 📋 可還原快照索引表 (Available Snapshots)

| 備份日期 | 備份編號 (Backup ID) | 類型 | 封裝大小 | 差異變更數 | SHA-256 (首12碼) | 一鍵還原指令 (Quick Restore Command) |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **2026-11-13** | `hermes_diff_20261113_030043` | `DIFFERENTIAL` | 305.97 MB | 27 個檔案 | `b2b2f1cf8737...` | `bash scripts/restore_diff.sh hermes_diff_20261113_030043` |
| **2026-11-12** | `hermes_diff_20261112_030042` | `DIFFERENTIAL` | 267.91 MB | 30 個檔案 | `c6290f685249...` | `bash scripts/restore_diff.sh hermes_diff_20261112_030042` |
| **2026-11-11** | `hermes_diff_20261111_030020` | `DIFFERENTIAL` | 224.07 MB | 5 個檔案 | `483fff135de0...` | `bash scripts/restore_diff.sh hermes_diff_20261111_030020` |
| **2026-11-10** | `hermes_diff_20261110_104438` | `DIFFERENTIAL` | 213.99 MB | 2 個檔案 | `ce24ae7ae8e9...` | `bash scripts/restore_diff.sh hermes_diff_20261110_104438` |

---

## 🔄 災難復原操作指引 (Disaster Recovery Guide)

### 1. 還原指定某一天的差異快照
在終端機執行對應日期的還原指令：
```bash
bash /Users/howard/Desktop/HermesAgent/PortFilio/Hermes-Backup/scripts/restore_diff.sh hermes_diff_20261113_030043
```

### 2. 一鍵還原至最新快照 (Default Latest)
不帶參數直接執行即自動選取最新一筆差異快照：
```bash
bash /Users/howard/Desktop/HermesAgent/PortFilio/Hermes-Backup/scripts/restore_diff.sh
```

### 3. 還原流程自動防護機制
1. **自動建立緊急快照**：在還原前自動備份當前 `~/.hermes`，避免二次覆蓋風險。
2. **原子性核心狀態恢復**：恢復 SQLite 資料庫（`state.db`、`projects.db`）、全套 Skills 與記憶庫。
3. **工作區差異增量復原**：將該日備份的專案異動檔案精準寫回原工作區路徑。
4. **系統完整性檢查**：自動執行 `hermes doctor` 驗證修復狀態。

---

### 🔒 資安與隱私防護保證
- 本表由自動化引擎每日同步至 GitHub，僅包含**備份索引元數據**與**校驗碼**。
- 所有含機密 Token 之實體壓縮檔與 `.env` 均受到嚴格本機隔離保存（`chmod 600`，本機路徑 `~/Hermes_Backups/`），絕不外流至公開儲存庫。
