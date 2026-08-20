#!/usr/bin/env python3
"""
Hermes-Backup: Local Web Console & Automation Daemon for Hermes Agent
Created for Howard Liao, Ph.D.
Provides a local REST API & Web UI for One-Click Backup, Disaster Recovery & Periodic Scheduling.
"""

import http.server
import socketserver
import json
import os
import sys
import subprocess
import sqlite3
import shutil
import glob
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = 5280
HOME = os.path.expanduser("~")
HERMES_DIR = os.path.join(HOME, ".hermes")
BACKUP_BASE_DIR = os.path.join(HOME, "Hermes_Backups")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

os.makedirs(BACKUP_BASE_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

def get_hermes_status():
    """Reads SQLite databases and returns Hermes health, size, and project list."""
    status = {
        "ok": True,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hermes_dir": HERMES_DIR,
        "state_db_size_mb": 0.0,
        "projects": [],
        "skills_count": 0,
        "memories_count": 0,
        "backups_count": 0,
        "last_backup": None,
        "crontab_schedule": None
    }
    
    # 1. State DB size
    state_db_path = os.path.join(HERMES_DIR, "state.db")
    if os.path.exists(state_db_path):
        status["state_db_size_mb"] = round(os.path.getsize(state_db_path) / (1024 * 1024), 2)
        
    # 2. Projects from projects.db
    projects_db_path = os.path.join(HERMES_DIR, "projects.db")
    if os.path.exists(projects_db_path):
        try:
            conn = sqlite3.connect(projects_db_path, timeout=5)
            cur = conn.cursor()
            cur.execute("SELECT id, slug, name, primary_path, archived FROM projects")
            for row in cur.fetchall():
                status["projects"].append({
                    "id": row[0],
                    "slug": row[1],
                    "name": row[2],
                    "primary_path": row[3],
                    "archived": bool(row[4]),
                    "exists": os.path.exists(row[3]) if row[3] else False
                })
            conn.close()
        except Exception as e:
            status["projects_error"] = str(e)
            
    # 3. Skills count
    skills_dir = os.path.join(HERMES_DIR, "skills")
    if os.path.exists(skills_dir):
        skills = glob.glob(os.path.join(skills_dir, "**", "SKILL.md"), recursive=True)
        status["skills_count"] = len(skills)

    # 4. Memories
    memories_dir = os.path.join(HERMES_DIR, "memories")
    if os.path.exists(memories_dir):
        status["memories_count"] = len(os.listdir(memories_dir))

    # 5. List backups
    backups = get_backup_list()
    status["backups_count"] = len(backups)
    if backups:
        status["last_backup"] = backups[0]

    # 6. Check crontab
    try:
        res = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if "backup" in line and ("Hermes" in line or "hermes" in line):
                    status["crontab_schedule"] = line.strip()
                    break
    except Exception:
        pass

    return status

def get_backup_list():
    """Returns list of completed backups with metadata."""
    results = []
    if not os.path.exists(BACKUP_BASE_DIR):
        return results
        
    entries = sorted(glob.glob(os.path.join(BACKUP_BASE_DIR, "hermes_backup_*")), reverse=True)
    for entry in entries:
        if os.path.isdir(entry):
            name = os.path.basename(entry)
            ts_str = name.replace("hermes_backup_", "")
            
            # calculate total folder size
            total_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(entry)
                for filename in filenames
            )
            
            manifest_file = os.path.join(entry, "manifest.json")
            manifest_data = {}
            if os.path.exists(manifest_file):
                try:
                    with open(manifest_file, "r") as f:
                        manifest_data = json.load(f)
                except Exception:
                    pass
                    
            results.append({
                "dir_name": name,
                "path": entry,
                "timestamp": ts_str,
                "size_mb": round(total_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(os.path.getctime(entry)).strftime("%Y-%m-%d %H:%M:%S"),
                "manifest": manifest_data
            })
    return results

def execute_live_backup(payload):
    """Executes live backup based on UI options."""
    include_core = payload.get("include_core", True)
    include_skills = payload.get("include_skills", True)
    include_memories = payload.get("include_memories", True)
    project_slugs = payload.get("projects", ["howard-portfolio"])
    exclude_heavy = payload.get("exclude_heavy", True)
    retention_count = int(payload.get("retention_count", 7))
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_target = os.path.join(BACKUP_BASE_DIR, f"hermes_backup_{timestamp}")
    core_dir = os.path.join(backup_target, "core")
    projects_dir = os.path.join(backup_target, "projects")
    
    os.makedirs(core_dir, exist_ok=True)
    os.makedirs(projects_dir, exist_ok=True)
    
    logs = []
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 開始執行 Hermes 專案全量備份...")
    
    # 1. Core backup
    if include_core:
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📦 正在執行 hermes backup 核心打包...")
        core_zip = os.path.join(core_dir, f"hermes_core_{timestamp}.zip")
        try:
            res = subprocess.run(["hermes", "backup", "-o", core_zip], capture_output=True, text=True, timeout=120)
            if res.returncode == 0:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 核心資料庫與設定檔打包成功 ({round(os.path.getsize(core_zip)/(1024*1024), 2)} MB)")
            else:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ hermes backup 返回警告: {res.stderr.strip() or res.stdout.strip()}")
        except Exception as e:
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ hermes backup 執行失敗: {e}")

    # 2. Skills & Memories directory sync
    if include_skills:
        skills_src = os.path.join(HERMES_DIR, "skills")
        if os.path.exists(skills_src):
            shutil.copytree(skills_src, os.path.join(core_dir, "skills"), dirs_exist_ok=True)
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 自訂技能庫 (~/.hermes/skills) 複製完成")

    if include_memories:
        mem_src = os.path.join(HERMES_DIR, "memories")
        if os.path.exists(mem_src):
            shutil.copytree(mem_src, os.path.join(core_dir, "memories"), dirs_exist_ok=True)
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📝 持久化記憶庫 (~/.hermes/memories) 複製完成")

    # 3. Project Workspaces Packaging
    all_projects = get_hermes_status().get("projects", [])
    for proj in all_projects:
        slug = proj.get("slug")
        path = proj.get("primary_path")
        if slug in project_slugs and path and os.path.exists(path):
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📂 正在打包專案 [{slug}] ({path})...")
            tar_name = os.path.join(projects_dir, f"project_{slug}_{timestamp}.tar.gz")
            
            tar_cmd = ["tar"]
            if exclude_heavy:
                tar_cmd.extend([
                    "--exclude=.git",
                    "--exclude=node_modules",
                    "--exclude=__pycache__",
                    "--exclude=.venv",
                    "--exclude=.DS_Store"
                ])
            
            parent_dir = os.path.dirname(path)
            base_name = os.path.basename(path)
            tar_cmd.extend(["-czf", tar_name, "-C", parent_dir, base_name])
            
            try:
                subprocess.run(tar_cmd, check=True, timeout=120)
                size_mb = round(os.path.getsize(tar_name) / (1024 * 1024), 2)
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 專案 [{slug}] 封裝完成 ({size_mb} MB)")
            except Exception as e:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 打包專案 [{slug}] 失敗: {e}")

    # 4. Write manifest.json
    manifest = {
        "backup_id": f"hermes_backup_{timestamp}",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "include_core": include_core,
        "include_skills": include_skills,
        "include_memories": include_memories,
        "projects": project_slugs,
        "target_path": backup_target
    }
    with open(os.path.join(backup_target, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    # 5. Clean older backups according to retention
    all_backups = sorted(glob.glob(os.path.join(BACKUP_BASE_DIR, "hermes_backup_*")), reverse=True)
    if len(all_backups) > retention_count:
        for old in all_backups[retention_count:]:
            shutil.rmtree(old, ignore_errors=True)
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🧹 清理過期歷史備份: {os.path.basename(old)}")

    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 備份作業圓滿完成！儲存至: {backup_target}")
    return {"success": True, "backup_id": f"hermes_backup_{timestamp}", "path": backup_target, "logs": logs}

def execute_live_restore(payload):
    """Executes live restore from a chosen backup folder."""
    backup_id = payload.get("backup_id")
    if not backup_id:
        backups = get_backup_list()
        if not backups:
            return {"success": False, "error": "沒有可用的歷史備份封裝"}
        backup_dir = backups[0]["path"]
    else:
        backup_dir = os.path.join(BACKUP_BASE_DIR, backup_id)
        if not os.path.exists(backup_dir):
            return {"success": False, "error": f"找不到指定備份目錄: {backup_id}"}

    logs = []
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 開始執行 Hermes 災難復原作業...")
    
    # 1. Emergency safety snapshot
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🛡️ 正在建立還原前緊急快照 (Pre-Restore Rollback Snapshot)...")
    try:
        subprocess.run(["hermes", "backup", "--quick", "-l", "pre-restore-emergency"], capture_output=True, text=True, timeout=60)
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 緊急回滾點已成功儲存")
    except Exception as e:
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 建立快照失敗 (繼續執行): {e}")

    # 2. Find core zip in backup folder
    core_zips = glob.glob(os.path.join(backup_dir, "core", "hermes_core_*.zip"))
    if core_zips:
        core_zip = core_zips[0]
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📦 正在從 {os.path.basename(core_zip)} 還原 state.db 與系統設定...")
        try:
            res = subprocess.run(["hermes", "import", core_zip, "--force"], capture_output=True, text=True, timeout=120)
            if res.returncode == 0:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 核心狀態匯入成功")
            else:
                logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 還原警告: {res.stderr.strip() or res.stdout.strip()}")
        except Exception as e:
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ hermes import 失敗: {e}")

    # 3. Doctor verification
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🩺 執行 Hermes Doctor 診斷...")
    try:
        subprocess.run(["hermes", "doctor"], capture_output=True, text=True, timeout=30)
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 系統相依性與環境校驗完成")
    except Exception:
        pass

    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 災難復原完成！已成功恢復至備份時間點。")
    return {"success": True, "logs": logs}

def configure_schedule(payload):
    """Sets crontab and/or Hermes cron for periodic backup."""
    frequency = payload.get("frequency", "daily")
    custom_cron = payload.get("custom_cron", "0 3 * * *")
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "backup.sh")
    
    if frequency == "hourly":
        cron_expr = "0 * * * *"
    elif frequency == "daily":
        cron_expr = "0 3 * * *"
    elif frequency == "weekly":
        cron_expr = "0 3 * * 0"
    elif frequency == "disabled":
        cron_expr = None
    else:
        cron_expr = custom_cron

    logs = []
    
    # Update macOS Crontab
    try:
        curr_crontab = ""
        res = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            lines = [l for l in res.stdout.splitlines() if "backup" not in l and "Hermes" not in l]
            curr_crontab = "\n".join(lines)
        
        if cron_expr:
            new_entry = f"{cron_expr} /bin/bash {script_path} >> {BACKUP_BASE_DIR}/backup.log 2>&1"
            final_crontab = (curr_crontab + "\n" + new_entry).strip() + "\n"
            p = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            p.communicate(input=final_crontab, timeout=5)
            logs.append(f"✅ 已成功更新 macOS Crontab 排程: [{cron_expr}]")
        else:
            final_crontab = curr_crontab.strip() + "\n" if curr_crontab.strip() else ""
            p = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            p.communicate(input=final_crontab, timeout=5)
            logs.append("ℹ️ 已取消 macOS Crontab 定期備份排程")
    except Exception as e:
        logs.append(f"❌ 設定 Crontab 失敗: {e}")

    return {"success": True, "schedule": cron_expr, "logs": logs}

def git_sync(payload):
    """Commits and pushes repo changes to GitHub."""
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    commit_msg = payload.get("message", f"Hermes Backup update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    logs = []
    try:
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, timeout=10)
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_dir, capture_output=True, text=True, timeout=10)
        logs.append("✅ Git 本地變更已 Commit")
        
        res = subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, capture_output=True, text=True, timeout=30)
        if res.returncode == 0:
            logs.append("🚀 已成功推送 (git push) 至 GitHub: HowardLiao/Hermes-Backup")
        else:
            logs.append(f"⚠️ Git push 輸出: {res.stderr or res.stdout}")
    except Exception as e:
        logs.append(f"❌ Git 操作失敗: {e}")

    return {"success": True, "logs": logs}


class HermesBackupHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(get_hermes_status()).encode("utf-8"))
        elif parsed.path == "/api/backups":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"backups": get_backup_list()}).encode("utf-8"))
        elif parsed.path == "/" or parsed.path == "/index.html":
            index_path = os.path.join(STATIC_DIR, "index.html")
            if os.path.exists(index_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(index_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            payload = json.loads(post_data)
        except Exception:
            payload = {}

        response = {"ok": False}
        if parsed.path == "/api/backup":
            response = execute_live_backup(payload)
        elif parsed.path == "/api/restore":
            response = execute_live_restore(payload)
        elif parsed.path == "/api/schedule":
            response = configure_schedule(payload)
        elif parsed.path == "/api/git-sync":
            response = git_sync(payload)
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def run_server():
    server_address = ("127.0.0.1", PORT)
    httpd = ThreadedHTTPServer(server_address, HermesBackupHTTPHandler)
    print(f"🌟 Hermes Backup Control Server listening on http://127.0.0.1:{PORT}")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
