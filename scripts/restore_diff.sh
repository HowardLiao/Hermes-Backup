#!/bin/bash
# ==============================================================================
# Hermes-Backup: Automated Standalone Differential Restore Script
# Author: Howard Liao, Ph.D.
# ==============================================================================
set -e

BACKUP_BASE="$HOME/Hermes_Backups/diff_backups"
TARGET_INPUT="$1"

if [ -z "$TARGET_INPUT" ]; then
    # 預設尋找最新一筆差異備份
    TARGET_DIR=$(ls -dt "$BACKUP_BASE"/hermes_diff_* 2>/dev/null | grep -v "\.tar\.gz" | head -n 1)
else
    if [ -d "$TARGET_INPUT" ]; then
        TARGET_DIR="$TARGET_INPUT"
    elif [ -d "$BACKUP_BASE/$TARGET_INPUT" ]; then
        TARGET_DIR="$BACKUP_BASE/$TARGET_INPUT"
    elif [ -f "$BACKUP_BASE/$TARGET_INPUT.tar.gz" ]; then
        TARGET_DIR="$BACKUP_BASE/$TARGET_INPUT"
        mkdir -p "$TARGET_DIR"
        tar -xzf "$BACKUP_BASE/$TARGET_INPUT.tar.gz" -C "$BACKUP_BASE"
    else
        echo "❌ 找不到指定的備份目錄或檔案: $TARGET_INPUT"
        exit 1
    fi
fi

if [ -z "$TARGET_DIR" ] || [ ! -d "$TARGET_DIR" ]; then
    echo "❌ 找不到任何有效的差異備份目錄！"
    exit 1
fi

BACKUP_ID=$(basename "$TARGET_DIR")
echo "=========================================================="
echo "🔄 開始執行 Hermes 差異快照還原作業"
echo "📦 還原目標: $BACKUP_ID"
echo "📂 實體路徑: $TARGET_DIR"
echo "=========================================================="

# 1. 建立當前狀態緊急防護回滾點 (Rollback snapshot)
EMERGENCY_DIR="$HOME/Hermes_Backups/pre_restore_emergency_$(date +%Y%m%d_%H%M%S)"
echo "🛡️ 1/4 建立還原前緊急回滾快照至: $EMERGENCY_DIR ..."
mkdir -p "$EMERGENCY_DIR"
[ -f "$HOME/.hermes/state.db" ] && cp "$HOME/.hermes/state.db" "$EMERGENCY_DIR/"
[ -f "$HOME/.hermes/projects.db" ] && cp "$HOME/.hermes/projects.db" "$EMERGENCY_DIR/"
[ -f "$HOME/.hermes/config.yaml" ] && cp "$HOME/.hermes/config.yaml" "$EMERGENCY_DIR/"
[ -f "$HOME/.hermes/.env" ] && cp "$HOME/.hermes/.env" "$EMERGENCY_DIR/"

# 2. 還原核心資料庫與設定檔
echo "📦 2/4 還原 Hermes 核心資料庫、設定檔、Skills 與記憶庫..."
CORE_DIR="$TARGET_DIR/core"
if [ -d "$CORE_DIR" ]; then
    [ -f "$CORE_DIR/state.db" ] && cp -v "$CORE_DIR/state.db" "$HOME/.hermes/state.db"
    [ -f "$CORE_DIR/projects.db" ] && cp -v "$CORE_DIR/projects.db" "$HOME/.hermes/projects.db"
    [ -f "$CORE_DIR/kanban.db" ] && cp -v "$CORE_DIR/kanban.db" "$HOME/.hermes/kanban.db"
    [ -f "$CORE_DIR/config.yaml" ] && cp -v "$CORE_DIR/config.yaml" "$HOME/.hermes/config.yaml"
    [ -f "$CORE_DIR/.env" ] && cp -v "$CORE_DIR/.env" "$HOME/.hermes/.env"
    
    if [ -d "$CORE_DIR/skills" ]; then
        cp -R "$CORE_DIR/skills"/* "$HOME/.hermes/skills/" 2>/dev/null || true
    fi
    if [ -d "$CORE_DIR/memories" ]; then
        cp -R "$CORE_DIR/memories"/* "$HOME/.hermes/memories/" 2>/dev/null || true
    fi
    if [ -d "$CORE_DIR/line-setup" ]; then
        cp -R "$CORE_DIR/line-setup"/* "$HOME/.hermes/line-setup/" 2>/dev/null || true
    fi
fi

# 3. 還原工作區異動檔案 (Workspaces Differential Restore)
echo "📂 3/4 還原專案工作區差異檔案..."
WORKSPACES_DIR="$TARGET_DIR/workspaces"
if [ -d "$WORKSPACES_DIR" ] && [ -f "$HOME/.hermes/projects.db" ]; then
    for proj_dir in "$WORKSPACES_DIR"/*; do
        if [ -d "$proj_dir" ]; then
            slug=$(basename "$proj_dir")
            ppath=$(sqlite3 "$HOME/.hermes/projects.db" "SELECT primary_path FROM projects WHERE slug='$slug' LIMIT 1;")
            if [ -n "$ppath" ] && [ -d "$ppath" ]; then
                echo "  -> 還原專案 [$slug] 異動檔案至 $ppath ..."
                cp -R "$proj_dir"/* "$ppath/"
            fi
        fi
    done
fi

# 4. 驗證與診斷
echo "🩺 4/4 執行 Hermes Doctor 診斷..."
hermes doctor || true
echo "=========================================================="
echo "✅ 差異快照 $BACKUP_ID 還原作業順利完成！"
echo "=========================================================="
