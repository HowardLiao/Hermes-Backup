# Hermes-Backup 🚀

Enterprise-Grade Backup, Disaster Recovery & Automation Studio for **Hermes Agent**.

Created by **Howard Liao, Ph.D.** for high-availability agentic governance and zero data loss SLA.

---

## 🌟 Key Features

- **⚡ 1-Click Backup (一鍵備份)**:
  - Backs up Hermes core (`state.db`, `projects.db`, `kanban.db`, `config.yaml`, `sessions/`).
  - Automatically discovers and packages all active project workspaces (`howard-portfolio`, `desktop`, etc.) while excluding bulky directories (`node_modules`, `.venv`, `__pycache__`, `.git`).
  - Preserves custom Skills (`~/.hermes/skills/`) and long-term memory (`~/.hermes/memories/`, `SOUL.md`).
  - Generates JSON Manifest with SHA-256 data integrity checksums.

- **🔄 1-Click Disaster Recovery (一鍵災難復原)**:
  - Pre-flight verification & rollback-safe emergency snapshot creation.
  - 100% atomic recovery using `hermes import <archive> --force`.
  - Automated `hermes doctor` diagnostic health checks.

- **⏰ Periodic Backup Scheduler (週期備份排程)**:
  - Visual selector for Hourly, Daily (03:00 AM), Weekly, or Custom Cron schedules.
  - Automatically synchronizes with macOS `crontab`.
  - Automatic retention policy (keeps last 7 backups, cleans old snapshots).

- **☁️ Cloud & GitHub Synchronization**:
  - Direct integration with GitHub repository `HowardLiao/Hermes-Backup`.

---

## 🖥️ Local Web Console (Interactive UI)

Start the local console server:

```bash
python3 /Users/howardliao/Hermes-Backup/server.py
```

Then open `http://localhost:5280` in any browser or preview pane.

---

## 🛠️ CLI Standalone Usage

### 1. Manual Backup
```bash
bash /Users/howardliao/Hermes-Backup/scripts/backup.sh
```

### 2. Disaster Recovery Restore
```bash
# Restore latest snapshot
bash /Users/howardliao/Hermes-Backup/scripts/restore.sh

# Restore specific snapshot
bash /Users/howardliao/Hermes-Backup/scripts/restore.sh ~/Hermes_Backups/hermes_backup_YYYYMMDD_HHMMSS
```

---

## 📋 Crontab Format

To run daily at 3:00 AM:
```cron
0 3 * * * /bin/bash /Users/howardliao/Hermes-Backup/scripts/backup.sh >> /Users/howardliao/Hermes_Backups/backup.log 2>&1
```

---

## 📄 License

MIT License. Designed for Hermes Agent Ecosystem.
