#!/bin/sh
# One-time preparation of a fresh Ubuntu server for RauteOS. Safe to run again.
#   ssh root@SERVER 'sh -s' < deploy/setup.sh
set -eu

# The image build (npm + uv) and a few `claude` processes during the sweep can
# outgrow 4 GB for a moment; swap turns that into slowness instead of a kill.
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -yq ca-certificates curl git ufw unattended-upgrades sqlite3
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi

ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp
ufw --force enable

# Keys only: the root password Hetzner mailed out stops working over SSH.
# sshd takes the first value it reads, and cloud-init's drop-in is read first.
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf
systemctl reload ssh || systemctl reload sshd

mkdir -p /srv/rauteos/data
[ -d /srv/rauteos/repo ] || git clone https://github.com/rapha-raffaelo/rauteOS.git /srv/rauteos/repo
[ -f /srv/rauteos/.env ] || install -m 600 /dev/null /srv/rauteos/.env

# Nightly consistent copy of the database beside it; Hetzner's server backups
# then carry it off the machine. Seven days kept.
cat > /etc/cron.d/rauteos-backup <<'EOF'
30 3 * * * root mkdir -p /srv/rauteos/backups && sqlite3 /srv/rauteos/data/newspulse.db ".backup /srv/rauteos/backups/newspulse-$(date +\%u).db"
EOF
echo "ready"
