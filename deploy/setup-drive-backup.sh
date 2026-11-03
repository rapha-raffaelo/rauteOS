#!/bin/sh
# One-time connection of the nightly backup to Google Drive. Safe to run again.
#   ssh -t root@SERVER 'sh /srv/rauteos/repo/deploy/setup-drive-backup.sh'
#
# Asks for one thing: the Drive token. Make it on a computer with a browser:
#   brew install rclone
#   rclone authorize "drive" "eyJzY29wZSI6ImRyaXZlLmZpbGUifQ"
# sign in as r.mankopf@raute-kopf.com, and paste the {"access_token":...} line it
# prints. The scope is drive.file: rclone sees only the files it created itself,
# never the rest of the Drive.
set -eu

command -v rclone >/dev/null || { apt-get update -q && apt-get install -yq rclone; }
command -v sqlite3 >/dev/null || apt-get install -yq sqlite3

printf 'Drive token ({"access_token":...}): '
read -r TOKEN
rclone config create rauteos-drive drive scope=drive.file token="$TOKEN" >/dev/null

if rclone config show rauteos-backup >/dev/null 2>&1; then
  echo "Encryption already set up; the existing key is kept."
else
  KEY=$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | cut -c1-32)
  SALT=$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | cut -c1-32)
  rclone config create rauteos-backup crypt remote=rauteos-drive:RauteOS-Backups \
    password="$(rclone obscure "$KEY")" password2="$(rclone obscure "$SALT")" >/dev/null
  echo
  echo "=== Store both in the password manager. Without them no backup can be opened. ==="
  echo "RauteOS backup key:  $KEY"
  echo "RauteOS backup salt: $SALT"
  echo "==================================================================================="
fi

cat > /etc/cron.d/rauteos-drive-backup <<'EOF'
45 3 * * * root sh /srv/rauteos/repo/deploy/backup-drive.sh >> /var/log/rauteos-drive-backup.log 2>&1
EOF

echo "Test upload now ..."
sh /srv/rauteos/repo/deploy/backup-drive.sh
rclone ls rauteos-backup:daily
echo "done: nightly at 03:45, 30 days kept, plus the 1st of every month."
