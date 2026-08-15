#!/usr/bin/env bash
# One-time bootstrap for a fresh Ubuntu VM (written for Oracle Cloud's
# "Always Free" Ampere A1 shape — 2 OCPU/12GB as of mid-2026 — but works on
# any Ubuntu 22.04/24.04 host). Run this ON the VM, as a user with sudo:
#   curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/infrastructure/vm/setup.sh | bash
# or clone the repo first and run it locally — either way it's idempotent,
# safe to re-run.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/mr-guptazii/LangAdapt-AI.git}"
APP_DIR="${APP_DIR:-$HOME/lingoadapt}"

echo "==> Installing Docker Engine + Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  echo "    Docker installed. You may need to log out/in for group membership to apply."
fi

echo "==> Opening the OS-level firewall for 22/80/443"
# Ubuntu cloud images ship with ufw inactive by default, but enable it
# defensively rather than assume — and this is ALSO not the only firewall in
# the way: OCI's cloud-level Security List/NSG for this VM's subnet must
# separately allow ingress on 80/443 (22 is usually pre-opened for SSH) via
# the OCI Console — ufw rules here do nothing if the cloud firewall blocks the
# packet first. This trips up nearly everyone doing a first OCI deploy.
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow 22/tcp
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw --force enable
fi

echo "==> Cloning the repo"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull
else
  git clone "$REPO_URL" "$APP_DIR"
fi

ENV_FILE="$APP_DIR/apps/api/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "==> Creating $ENV_FILE from the template — EDIT THIS before continuing:"
  cp "$APP_DIR/apps/api/.env.example" "$ENV_FILE"
  echo "    - Set JWT_SECRET to a long random value (e.g. \`openssl rand -hex 32\`)"
  echo "    - Set POSTGRES_PASSWORD and REDIS_PASSWORD to real random values"
  echo "    - Set DOMAIN to your real domain for automatic HTTPS (or leave blank for plain HTTP on the bare IP)"
  echo "    - Set LLM_PROVIDER (+ keys) for a real provider, or leave as 'mock'"
  echo ""
  echo "Edit $ENV_FILE now, then re-run this script (or just run the compose command below)."
  exit 0
fi

echo "==> Starting the stack"
cd "$APP_DIR"
docker compose -f infrastructure/vm/docker-compose.prod.yml --env-file apps/api/.env up -d --build

echo "==> Running seed data (optional — comment out if you don't want the demo account)"
docker compose -f infrastructure/vm/docker-compose.prod.yml --env-file apps/api/.env exec -T api python scripts/seed.py || true

echo "==> Done. Check status with:"
echo "    docker compose -f infrastructure/vm/docker-compose.prod.yml ps"
echo "    curl http://localhost/health"
