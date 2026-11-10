#!/usr/bin/env python3
"""
Hermes-Backup: Daily Differential Backup & GitHub Sync Engine
Author: Howard Liao, Ph.D.
Retention Policy: Maximum 15 Days Rolling Differential Snapshots
Sync Target: HowardLiao/Hermes-Backup (GitHub)
"""

import os
import sys
import time
import json
import glob
import shutil
import tarfile
import hashlib
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Paths
HOME = os.path.expanduser("~")
HERMES_DIR = os.path.join(HOME, ".hermes")
BACKUP_BASE_DIR = os.path.join(HOME, "Hermes_Backups")
DIFF_BASE_DIR = os.path.join(BACKUP_BASE_DIR, "diff_backups")
REPO_DIR = os.path.join(HOME, "Desktop", "HermesAgent", "PortFilio", "Hermes-Backup")
LOG_FILE = os.path.join(BACKUP_BASE_DIR, "backup.log")

MAX_RETENTION_DAYS = 15

os.makedirs(BACKUP_BASE_DIR, exist_ok=True)
os.makedirs(DIFF_BASE_DIR, exist_ok=True)


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def calculate_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_active_projects():
    """Fetches active non-archived projects from projects.db"""
    projects = []
    projects_db_path = os.path.join(HERMES_DIR, "projects.db")
    if os.path.exists(projects_db_path):
        try:
            conn = sqlite3.connect(projects_db_path, timeout=5)
            cur = conn.cursor()
            cur.execute("SELECT slug, name, primary_path FROM projects WHERE archived=0")
            for slug, name, ppath in cur.fetchall():
                if ppath and os.path.exists(ppath):
                    projects.append({"slug": slug, "name": name, "path": ppath})
            conn.close()
        except Exception as e:
            log(f"⚠️ 無法讀取 projects.db: {e}")
    return projects


def find_differential_files(project_path: str, since_timestamp: float):
    """Finds files modified in project_path since given timestamp (default 24h)"""
    EXCLUDE_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", ".DS_Store"}
    changed_files = []
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f in EXCLUDE_DIRS:
                continue
            fp = os.path.join(root, f)
            try:
                mtime = os.path.getmtime(fp)
                if mtime >= since_timestamp:
                    rel_p = os.path.relpath(fp, project_path)
                    changed_files.append((fp, rel_p, mtime, os.path.getsize(fp)))
            except OSError:
                continue
    return changed_files


def run_differential_backup():
    now = datetime.now()
    ts_str = now.strftime("%Y%m%d_%H%M%S")
    date_str = now.strftime("%Y-%m-%d")
    backup_id = f"hermes_diff_{ts_str}"
    target_dir = os.path.join(DIFF_BASE_DIR, backup_id)
    os.makedirs(target_dir, exist_ok=True)

    log(f"🚀 開始執行每日差異備份: {backup_id} (保留上限: {MAX_RETENTION_DAYS} 天)")

    # 1. 備份核心狀態 (Core Configuration & Databases)
    core_dir = os.path.join(target_dir, "core")
    os.makedirs(core_dir, exist_ok=True)

    # 備份 SQLite DBs (以 SQLite backup API 確保交易一致性)
    for db_name in ["state.db", "projects.db", "kanban.db"]:
        src_db = os.path.join(HERMES_DIR, db_name)
        if os.path.exists(src_db):
            dst_db = os.path.join(core_dir, db_name)
            try:
                sconn = sqlite3.connect(src_db)
                dconn = sqlite3.connect(dst_db)
                sconn.backup(dconn)
                sconn.close()
                dconn.close()
            except Exception:
                shutil.copy2(src_db, dst_db)

    # 備份重要設定與金鑰 (僅本機保存，安全防護)
    for cfg in ["config.yaml", ".env"]:
        src_cfg = os.path.join(HERMES_DIR, cfg)
        if os.path.exists(src_cfg):
            dst_cfg = os.path.join(core_dir, cfg)
            shutil.copy2(src_cfg, dst_cfg)
            os.chmod(dst_cfg, 0o600)

    # 備份 Skills, Memories, line-setup
    for d in ["skills", "memories", "line-setup"]:
        src_d = os.path.join(HERMES_DIR, d)
        if os.path.exists(src_d):
            dst_d = os.path.join(core_dir, d)
            if os.path.exists(dst_d):
                shutil.rmtree(dst_d)
            shutil.copytree(src_d, dst_d)

    # 2. 差異比對工作區 (過去 24 小時異動檔案)
    since_ts = (now - timedelta(hours=24)).timestamp()
    projects = get_active_projects()
    total_changed_files = 0
    workspaces_dir = os.path.join(target_dir, "workspaces")
    os.makedirs(workspaces_dir, exist_ok=True)

    diff_summary = []
    for proj in projects:
        slug = proj["slug"]
        ppath = proj["path"]
        changed = find_differential_files(ppath, since_ts)
        if changed:
            total_changed_files += len(changed)
            proj_diff_dir = os.path.join(workspaces_dir, slug)
            os.makedirs(proj_diff_dir, exist_ok=True)
            for src_file, rel_file, mtime, fsize in changed:
                dst_file = os.path.join(proj_diff_dir, rel_file)
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                shutil.copy2(src_file, dst_file)
            diff_summary.append({
                "slug": slug,
                "name": proj["name"],
                "path": ppath,
                "changed_count": len(changed)
            })

    log(f"📦 核心配置打包完成，偵測到 {len(diff_summary)} 個專案共 {total_changed_files} 個差異變更檔案。")

    # 3. 封裝單一差異壓縮檔 (Differential Tarball)
    archive_filename = f"{backup_id}.tar.gz"
    archive_path = os.path.join(DIFF_BASE_DIR, archive_filename)
    log(f"🗜️ 正在封裝差異壓縮檔: {archive_filename} ...")
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(target_dir, arcname=backup_id)

    archive_size = os.path.getsize(archive_path)
    archive_sha256 = calculate_sha256(archive_path)

    # 4. 寫入 Manifest
    manifest_data = {
        "backup_id": backup_id,
        "date": date_str,
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "type": "DIFFERENTIAL",
        "retention_policy": f"Rolling {MAX_RETENTION_DAYS} Days",
        "archive_file": archive_filename,
        "archive_path": archive_path,
        "archive_size_bytes": archive_size,
        "archive_size_human": human_size(archive_size),
        "sha256": archive_sha256,
        "total_changed_files": total_changed_files,
        "diff_projects": diff_summary,
        "core_included": ["state.db", "projects.db", "kanban.db", "config.yaml", ".env", "skills", "memories", "line-setup"]
    }
    manifest_path = os.path.join(target_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    # 複製份到頂部備份目錄便於索引
    shutil.copy2(manifest_path, os.path.join(DIFF_BASE_DIR, f"{backup_id}_manifest.json"))

    # 5. 滾動刪除超過 15 天的舊備份 (Retention Policy: Max 15 Days)
    prune_old_backups()

    # 6. 生成最新 15 天還原表 (Restore Table)
    restore_table_md = generate_restore_table()

    # 7. 同步更新 GitHub Repository (HowardLiao/Hermes-Backup)
    sync_to_github(restore_table_md, now)

    log(f"✅ 每日差異備份與 GitHub 還原表同步全數完成！")
    return backup_id


def prune_old_backups():
    """嚴格保留最新的 15 天差異備份，過期的自動清理"""
    all_diff_dirs = sorted(glob.glob(os.path.join(DIFF_BASE_DIR, "hermes_diff_*")), reverse=True)
    # 過濾出真正的目錄
    valid_dirs = [d for d in all_diff_dirs if os.path.isdir(d)]
    
    if len(valid_dirs) > MAX_RETENTION_DAYS:
        to_delete = valid_dirs[MAX_RETENTION_DAYS:]
        for d in to_delete:
            b_id = os.path.basename(d)
            log(f"🧹 輪轉清理超過 {MAX_RETENTION_DAYS} 天的舊備份: {b_id}")
            shutil.rmtree(d, ignore_errors=True)
            tar_file = os.path.join(DIFF_BASE_DIR, f"{b_id}.tar.gz")
            if os.path.exists(tar_file):
                os.remove(tar_file)
            manifest_file = os.path.join(DIFF_BASE_DIR, f"{b_id}_manifest.json")
            if os.path.exists(manifest_file):
                os.remove(manifest_file)


def get_all_manifests():
    """載入目前所有的 15 天內備份清單"""
    manifests = []
    # 搜尋所有 manifest 檔案
    manifest_files = sorted(glob.glob(os.path.join(DIFF_BASE_DIR, "hermes_diff_*_manifest.json")), reverse=True)
    for mf in manifest_files:
        try:
            with open(mf, "r", encoding="utf-8") as f:
                data = json.load(f)
                manifests.append(data)
        except Exception:
            continue
    return manifests


def generate_restore_table() -> str:
    """生成漂亮的 Markdown 還原索引表"""
    manifests = get_all_manifests()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = []
    md.append("# 🛡️ Hermes Agent 15-Day Rolling Differential Backup & Restore Table")
    md.append("")
    md.append(f"> **最後同步時間 (Last Synced)**：`{now_str}` (CST / UTC+8)")
    md.append(f"> **保留政策 (Retention)**：嚴格保留最近 **{MAX_RETENTION_DAYS} 天** 差異備份，過期自動輪轉清理。")
    md.append(f"> **備份內容**：Hermes Core（狀態資料庫、設定檔、Skills、Memories、LINE Tunnel 守護架構）與全工作區 24H 差異異動。")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 📋 可還原快照索引表 (Available Snapshots)")
    md.append("")
    md.append("| 備份日期 | 備份編號 (Backup ID) | 類型 | 封裝大小 | 差異變更數 | SHA-256 (首12碼) | 一鍵還原指令 (Quick Restore Command) |")
    md.append("| :--- | :--- | :---: | :---: | :---: | :---: | :--- |")

    if not manifests:
        md.append("| - | 目前尚無備份記錄 | - | - | - | - | - |")
    else:
        for m in manifests:
            b_id = m.get("backup_id", "")
            date_col = m.get("date", "")
            b_type = m.get("type", "DIFF")
            size_col = m.get("archive_size_human", "N/A")
            changed_col = f"{m.get('total_changed_files', 0)} 個檔案"
            sha = m.get("sha256", "")[:12]
            restore_cmd = f"`bash scripts/restore_diff.sh {b_id}`"
            md.append(f"| **{date_col}** | `{b_id}` | `{b_type}` | {size_col} | {changed_col} | `{sha}...` | {restore_cmd} |")

    md.append("")
    md.append("---")
    md.append("")
    md.append("## 🔄 災難復原操作指引 (Disaster Recovery Guide)")
    md.append("")
    md.append("### 1. 還原指定某一天的差異快照")
    md.append("在終端機執行對應日期的還原指令：")
    md.append("```bash")
    if manifests:
        md.append(f"bash /Users/howard/Desktop/HermesAgent/PortFilio/Hermes-Backup/scripts/restore_diff.sh {manifests[0]['backup_id']}")
    else:
        md.append("bash /Users/howard/Desktop/HermesAgent/PortFilio/Hermes-Backup/scripts/restore_diff.sh <BACKUP_ID>")
    md.append("```")
    md.append("")
    md.append("### 2. 一鍵還原至最新快照 (Default Latest)")
    md.append("不帶參數直接執行即自動選取最新一筆差異快照：")
    md.append("```bash")
    md.append("bash /Users/howard/Desktop/HermesAgent/PortFilio/Hermes-Backup/scripts/restore_diff.sh")
    md.append("```")
    md.append("")
    md.append("### 3. 還原流程自動防護機制")
    md.append("1. **自動建立緊急快照**：在還原前自動備份當前 `~/.hermes`，避免二次覆蓋風險。")
    md.append("2. **原子性核心狀態恢復**：恢復 SQLite 資料庫（`state.db`、`projects.db`）、全套 Skills 與記憶庫。")
    md.append("3. **工作區差異增量復原**：將該日備份的專案異動檔案精準寫回原工作區路徑。")
    md.append("4. **系統完整性檢查**：自動執行 `hermes doctor` 驗證修復狀態。")
    md.append("")
    md.append("---")
    md.append("")
    md.append("### 🔒 資安與隱私防護保證")
    md.append("- 本表由自動化引擎每日同步至 GitHub，僅包含**備份索引元數據**與**校驗碼**。")
    md.append("- 所有含機密 Token 之實體壓縮檔與 `.env` 均受到嚴格本機隔離保存（`chmod 600`，本機路徑 `~/Hermes_Backups/`），絕不外流至公開儲存庫。")
    md.append("")

    content = "\n".join(md)

    # 寫入本機備份總表
    master_table_path = os.path.join(BACKUP_BASE_DIR, "RESTORE_MANIFEST.md")
    with open(master_table_path, "w", encoding="utf-8") as f:
        f.write(content)

    return content


def sync_to_github(restore_table_content: str, now: datetime):
    """將還原表同步上傳至 GitHub HowardLiao/Hermes-Backup"""
    if not os.path.exists(REPO_DIR):
        log(f"⚠️ 找不到 Git 專案目錄: {REPO_DIR}")
        return

    # 1. 寫入專屬還原清單檔案 RESTORE_TABLE.md
    target_table_path = os.path.join(REPO_DIR, "RESTORE_TABLE.md")
    with open(target_table_path, "w", encoding="utf-8") as f:
        f.write(restore_table_content)

    # 2. 更新 README.md，將最新的 15 天還原表動態注入
    readme_path = os.path.join(REPO_DIR, "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            readme_text = f.read()

        START_MARKER = "<!-- START_RESTORE_TABLE -->"
        END_MARKER = "<!-- END_RESTORE_TABLE -->"

        table_section = f"{START_MARKER}\n\n{restore_table_content}\n\n{END_MARKER}"

        if START_MARKER in readme_text and END_MARKER in readme_text:
            before = readme_text.split(START_MARKER)[0]
            after = readme_text.split(END_MARKER)[1]
            new_readme = before + table_section + after
        else:
            new_readme = readme_text + "\n\n" + table_section

        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(new_readme)

    # 3. Git Commit & Push
    try:
        log("🔄 正在同步還原表至 GitHub (HowardLiao/Hermes-Backup)...")
        subprocess.run(["git", "add", "RESTORE_TABLE.md", "README.md"], cwd=REPO_DIR, check=True)
        commit_msg = f"chore(backup): auto-sync 15-day differential restore table [{now.strftime('%Y-%m-%d %H:%M')}]"
        
        # 檢查是否有變更需要 commit
        status_res = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_DIR, capture_output=True, text=True)
        if status_res.stdout.strip():
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_DIR, check=True)
            push_res = subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, capture_output=True, text=True)
            if push_res.returncode == 0:
                log("✅ GitHub 同步推送成功！")
            else:
                log(f"⚠️ GitHub 推送失敗: {push_res.stderr}")
        else:
            log("ℹ️ 還原表內容無異動，無須提交。")
    except Exception as e:
        log(f"⚠️ Git 同步流程異常: {e}")


if __name__ == "__main__":
    run_differential_backup()
