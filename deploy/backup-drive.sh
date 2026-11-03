#!/bin/sh
# Nightly off-site copy of the RauteOS database to Google Drive, encrypted.
#   Run by /etc/cron.d/rauteos-drive-backup (installed by setup-drive-backup.sh).
#
# Only the database goes: it holds every mandate, profile, draft and logo. The
# `claude` login and /srv/rauteos/.env stay on the server; they are secrets, and
# a restore re-creates them by logging in again.
#
# The `rauteos-backup` remote is an rclone crypt over the Drive folder
# RauteOS-Backups: file contents and names are encrypted before they leave the
# machine, so the Drive holds nothing readable without the key.
set -eu

DB=/srv/rauteos/data/newspulse.db
WORK=/srv/rauteos/backups/drive
REMOTE=rauteos-backup:
DAYS_KEPT=30
STAMP=$(date +%Y-%m-%d)

mkdir -p "$WORK"
SNAP="$WORK/newspulse-$STAMP.db"
rm -f "$SNAP" "$SNAP.gz"

# A consistent copy while the app keeps writing, checked before it is trusted.
sqlite3 "$DB" ".backup '$SNAP'"
[ "$(sqlite3 "$SNAP" 'PRAGMA integrity_check;')" = "ok" ] || {
  echo "$(date -Is) integrity check failed, nothing uploaded" >&2; exit 1; }
gzip -9 "$SNAP"

rclone copyto "$SNAP.gz" "${REMOTE}daily/newspulse-$STAMP.db.gz"
# The first of each month is also kept for good.
[ "$(date +%d)" = "01" ] && rclone copyto "$SNAP.gz" "${REMOTE}monthly/newspulse-$STAMP.db.gz"
rclone delete --min-age "${DAYS_KEPT}d" "${REMOTE}daily"

rm -f "$SNAP.gz"
echo "$(date -Is) uploaded newspulse-$STAMP.db.gz"
