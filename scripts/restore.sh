#!/bin/bash
# ==============================================================================
# Hermes-Backup: Automated Standalone Disaster Restore Script
# Author: Howard Liao, Ph.D.
# ==============================================================================
set -e

BACKUP_TARGET="$1"

if [ -z "$BACKUP_TARGET" ]; then
    # find latest
    BACKUP_TARGET=$(ls -dt $HOME/Hermes_Backups/hermes_backup_* 2>/dev/null | head -n 1)
fi

if [ -z "$BACKUP_TARGET" ] || [ ! -d "$BACKUP_TARGET" ]; then
    echo "❌ 找不到有效的備份目錄: $BACKUP_TARGET"
    exit 1
fi

echo "🔄 開始執行 Hermes 災難復原作業 (來源: $BACKUP_TARGET)..."

# 1. Emergency snapshot
echo "🛡️ 建立還原前緊急回滾點..."
hermes backup --quick -l "pre-restore-emergency" || true

# 2. Find core zip
CORE_ZIP=$(ls "$BACKUP_TARGET/core"/hermes_core_*.zip 2>/dev/null | head -n 1)
if [ -n "$CORE_ZIP" ] && [ -f "$CORE_ZIP" ]; then
    echo "📦 匯入核心狀態: $CORE_ZIP..."
    hermes import "$CORE_ZIP" --force
fi

# 3. Restore projects if needed
# (Projects are kept in $BACKUP_TARGET/projects/)

echo "🩺 執行 Hermes Doctor 診斷..."
hermes doctor
hermes project list

echo "✅ 災難復原作業完成！"
