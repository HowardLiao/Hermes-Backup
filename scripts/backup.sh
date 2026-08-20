#!/bin/bash
# ==============================================================================
# Hermes-Backup: Automated Standalone Backup Script
# Author: Howard Liao, Ph.D.
# ==============================================================================
set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_BASE="$HOME/Hermes_Backups"
BACKUP_DIR="$BACKUP_BASE/hermes_backup_${TIMESTAMP}"
LOG_FILE="$BACKUP_BASE/backup.log"

mkdir -p "$BACKUP_DIR/core"
mkdir -p "$BACKUP_DIR/projects"
mkdir -p "$BACKUP_BASE"

echo "==========================================================" >> "$LOG_FILE"
echo "[${TIMESTAMP}] 🚀 開始執行 Hermes 專案自動化備份..." >> "$LOG_FILE"

# 1. Hermes Core Backup
echo "[${TIMESTAMP}] 📦 執行 hermes backup 核心打包..." >> "$LOG_FILE"
hermes backup -o "$BACKUP_DIR/core/hermes_core_${TIMESTAMP}.zip" >> "$LOG_FILE" 2>&1 || true

# 2. Skills & Memories
[ -d "$HOME/.hermes/skills" ] && cp -R "$HOME/.hermes/skills" "$BACKUP_DIR/core/skills_backup"
[ -d "$HOME/.hermes/memories" ] && cp -R "$HOME/.hermes/memories" "$BACKUP_DIR/core/memories_backup"

# 3. Dynamic Projects Scanning & Packaging
if [ -f "$HOME/.hermes/projects.db" ]; then
    sqlite3 "$HOME/.hermes/projects.db" "SELECT slug, primary_path FROM projects WHERE archived=0;" | while IFS='|' read -r slug path; do
        if [ -n "$path" ] && [ -d "$path" ]; then
            echo "[${TIMESTAMP}] 📂 打包專案: [${slug}] -> ${path}" >> "$LOG_FILE"
            tar --exclude='.git' \
                --exclude='node_modules' \
                --exclude='__pycache__' \
                --exclude='.venv' \
                --exclude='.DS_Store' \
                -czf "$BACKUP_DIR/projects/project_${slug}_${TIMESTAMP}.tar.gz" \
                -C "$(dirname "$path")" "$(basename "$path")" >> "$LOG_FILE" 2>&1 || true
        fi
    done
fi

# 4. Manifest
cat <<EOF > "$BACKUP_DIR/manifest.json"
{
  "backup_id": "hermes_backup_${TIMESTAMP}",
  "created_at": "$(date '+%Y-%m-%d %H:%M:%S')",
  "include_core": true,
  "include_skills": true,
  "include_memories": true,
  "target_path": "${BACKUP_DIR}"
}
EOF

# 5. Retention: keep last 7
cd "$BACKUP_BASE" && ls -dt hermes_backup_* | tail -n +8 | xargs rm -rf 2>/dev/null || true

echo "[${TIMESTAMP}] ✅ Hermes 備份完成！封裝路徑: ${BACKUP_DIR}" >> "$LOG_FILE"
