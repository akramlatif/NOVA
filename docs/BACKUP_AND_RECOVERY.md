# NOVA — Backup and Recovery Guide (v1.0.0)

This document describes how to safely back up, restore, and maintain NOVA's persistent memory, task ledger, and configuration.

---

## 1. Overview of Persistent State

All state in NOVA is stored in lightweight, self-contained files under the project root or the configured `data/` directory:

| Component | Storage Path | Description |
|---|---|---|
| **Memory Database** | `data/memory.db` | User preferences, long-term facts, task history, and conversation logs |
| **Audit Log** | `logs/audit.jsonl` | Append-only ledger of security events, auth attempts, and tool executions |
| **Active Environment** | `.env` | Local server tokens, model preferences, and sandboxing roots |
| **Downloaded Files** | `Downloads/` | Sandboxed downloads retrieved by the browser automation agent |

---

## 2. Backup Procedures

### Method A: Automated Backup Script
Run the automated backup utility to create a timestamped archive:
```powershell
# Create a backup folder
$BackupDir = "backups\backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $BackupDir -Force

# Copy database, config, and audit log
if (Test-Path "data\memory.db") { Copy-Item "data\memory.db" "$BackupDir\memory.db" }
if (Test-Path ".env") { Copy-Item ".env" "$BackupDir\.env" }
if (Test-Path "logs\audit.jsonl") { Copy-Item "logs\audit.jsonl" "$BackupDir\audit.jsonl" }

Write-Host "Backup created successfully in $BackupDir" -ForegroundColor Green
```

### Method B: Online SQLite Safe Backup
Since SQLite uses WAL (Write-Ahead Logging), you can create an atomic snapshot while NOVA is running:
```powershell
.\.venv\Scripts\python.exe -c "
import sqlite3, shutil, datetime
src = 'data/memory.db'
dst = f'backups/memory_snapshot_{datetime.datetime.now():%Y%m%d_%H%M%S}.db'
conn = sqlite3.connect(src)
bck = sqlite3.connect(dst)
with bck:
    conn.backup(bck)
conn.close()
bck.close()
print(f'Safe atomic snapshot saved to {dst}')
"
```

---

## 3. Restoration Procedure

To restore NOVA after hardware failure, data corruption, or system migration:

1. **Stop all active NOVA processes**:
   ```powershell
   Get-Process -Name python, tauri -ErrorAction SilentlyContinue | Stop-Process -Force
   ```
2. **Replace the target database**:
   ```powershell
   Copy-Item "backups\your_backup_folder\memory.db" "data\memory.db" -Force
   ```
3. **Restore configuration**:
   ```powershell
   Copy-Item "backups\your_backup_folder\.env" ".env" -Force
   ```
4. **Verify database integrity**:
   ```powershell
   .\.venv\Scripts\python.exe -c "
   import sqlite3
   conn = sqlite3.connect('data/memory.db')
   cur = conn.cursor()
   cur.execute('PRAGMA integrity_check;')
   print('Database status:', cur.fetchone()[0])
   conn.close()
   "
   ```
   *Expected output*: `Database status: ok`

---

## 4. Reset & Disaster Recovery

If you ever wish to completely wipe NOVA's memory and reset to factory settings:
```powershell
# Remove memory database (it will be regenerated automatically on startup)
Remove-Item "data\memory.db*" -Force

# Restart desktop
powershell -ExecutionPolicy Bypass -File .\scripts\run_desktop.ps1
```
