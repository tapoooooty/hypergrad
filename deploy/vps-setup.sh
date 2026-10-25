#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu 22.04/24.04 VPS.
# Usage (as root): bash deploy/vps-setup.sh
set -euo pipefail

APP_DIR=/opt/hypergrad

echo "Installing Docker and basic tools"
apt-get update -y
apt-get install -y ca-certificates curl git ufw unattended-upgrades
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi

echo "Firewall: SSH only. The dashboard stays on localhost; use an SSH tunnel."
ufw allow OpenSSH
ufw --force enable

echo "Automatic security updates"
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "Time sync (the oracle signs timestamps)"
timedatectl set-ntp true

mkdir -p "$APP_DIR"
if [ ! -f "$APP_DIR/docker-compose.yml" ]; then
  echo "Copy the project into $APP_DIR first, for example:"
  echo "  scp -r ./HIP-3/* root@SERVER:$APP_DIR/"
  exit 0
fi

cd "$APP_DIR"
[ -f .env ] || cp .env.example .env
mkdir -p state && chown -R 10001 state
chmod 600 .env

echo "Edit $APP_DIR/.env, then run:"
echo "  cd $APP_DIR && docker compose run --rm oracle doctor"
echo "  docker compose up -d"
