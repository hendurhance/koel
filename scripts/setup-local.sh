#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Koel — local environment bootstrap (no Docker required)
#
# Installs / starts Postgres 16 + Redis 7, installs uv, installs project deps,
# creates the dev database, copies .env if missing. Safe to re-run.
# -----------------------------------------------------------------------------
set -euo pipefail

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
say()    { echo -e "${BLUE}==>${NC} $*"; }
ok()     { echo -e "${GREEN}✓${NC} $*"; }
warn()   { echo -e "${YELLOW}!${NC} $*"; }
fail()   { echo -e "${RED}✗${NC} $*"; exit 1; }

# -----------------------------------------------------------------------------
# OS detection
# -----------------------------------------------------------------------------
OS="$(uname -s)"
case "$OS" in
  Darwin)  PLATFORM="mac" ;;
  Linux)
    if command -v apt-get >/dev/null 2>&1; then PLATFORM="debian"
    elif command -v dnf    >/dev/null 2>&1; then PLATFORM="fedora"
    else fail "Unsupported Linux distro. Install Postgres + Redis manually, then rerun."
    fi
    ;;
  *) fail "Unsupported OS: $OS" ;;
esac
ok "Platform: $PLATFORM"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
has() { command -v "$1" >/dev/null 2>&1; }

install_mac() {
  if ! has brew; then
    fail "Homebrew not found. Install from https://brew.sh first."
  fi

  if ! has psql; then
    say "Installing postgresql@16 via Homebrew..."
    brew install postgresql@16
    brew link --force postgresql@16 || true
  else ok "Postgres already installed"
  fi

  if ! brew services list | grep -q "postgresql@16.*started"; then
    say "Starting postgresql@16..."
    brew services start postgresql@16
    sleep 2
  else ok "Postgres already running"
  fi

  if ! has redis-cli; then
    say "Installing redis via Homebrew..."
    brew install redis
  else ok "Redis already installed"
  fi

  if ! brew services list | grep -q "^redis.*started"; then
    say "Starting redis..."
    brew services start redis
    sleep 1
  else ok "Redis already running"
  fi
}

install_debian() {
  say "Installing Postgres + Redis via apt..."
  sudo apt-get update
  sudo apt-get install -y postgresql postgresql-contrib redis-server
  sudo systemctl enable --now postgresql redis-server || true
}

install_fedora() {
  say "Installing Postgres + Redis via dnf..."
  sudo dnf install -y postgresql-server postgresql-contrib redis
  sudo postgresql-setup --initdb || true
  sudo systemctl enable --now postgresql redis || true
}

# -----------------------------------------------------------------------------
# 1. System packages
# -----------------------------------------------------------------------------
say "Checking system packages..."
case "$PLATFORM" in
  mac)    install_mac ;;
  debian) install_debian ;;
  fedora) install_fedora ;;
esac

# -----------------------------------------------------------------------------
# 2. uv
# -----------------------------------------------------------------------------
if ! has uv; then
  say "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # shellcheck disable=SC1091
  source "$HOME/.local/bin/env" 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
else
  ok "uv already installed ($(uv --version))"
fi

# -----------------------------------------------------------------------------
# 3. Project deps
# -----------------------------------------------------------------------------
say "Installing Python dependencies (uv sync)..."
uv sync --all-extras
ok "Dependencies installed"

# -----------------------------------------------------------------------------
# 4. Database + role
# -----------------------------------------------------------------------------
say "Ensuring Postgres role + databases exist..."
PG_USER="${POSTGRES_USER:-postgres}"
PG_PASS="${POSTGRES_PASSWORD:-postgres}"
PG_DB="${POSTGRES_DB:-koel}"
PG_TEST_DB="${POSTGRES_TEST_DB:-koel_test}"

# On mac, the default superuser is the current user; on Linux, it's `postgres`.
if [[ "$PLATFORM" == "mac" ]]; then
  ADMIN_PSQL=(psql -U "$USER" -d postgres)
else
  ADMIN_PSQL=(sudo -u postgres psql -d postgres)
fi

"${ADMIN_PSQL[@]}" -tAc "SELECT 1 FROM pg_roles WHERE rolname='${PG_USER}'" | grep -q 1 || \
  "${ADMIN_PSQL[@]}" -c "CREATE ROLE ${PG_USER} LOGIN SUPERUSER PASSWORD '${PG_PASS}';"

"${ADMIN_PSQL[@]}" -tAc "SELECT 1 FROM pg_database WHERE datname='${PG_DB}'" | grep -q 1 || \
  "${ADMIN_PSQL[@]}" -c "CREATE DATABASE ${PG_DB} OWNER ${PG_USER};"

"${ADMIN_PSQL[@]}" -tAc "SELECT 1 FROM pg_database WHERE datname='${PG_TEST_DB}'" | grep -q 1 || \
  "${ADMIN_PSQL[@]}" -c "CREATE DATABASE ${PG_TEST_DB} OWNER ${PG_USER};"

ok "Databases ready: ${PG_DB}, ${PG_TEST_DB}"

# -----------------------------------------------------------------------------
# 5. .env
# -----------------------------------------------------------------------------
if [[ ! -f .env ]]; then
  say "Creating .env from .env.example..."
  cp .env.example .env
  # Rewrite DATABASE_URL + REDIS_URL for localhost dev
  if [[ "$PLATFORM" == "mac" ]]; then
    SED_INPLACE=(sed -i '')
  else
    SED_INPLACE=(sed -i)
  fi
  "${SED_INPLACE[@]}" \
    -e "s|@postgres:5432|@localhost:5432|g" \
    -e "s|redis://redis:6379|redis://localhost:6379|g" \
    .env
  ok ".env created (edit as needed)"
else
  ok ".env already exists"
fi

# -----------------------------------------------------------------------------
# 6. Migrations (skipped until Phase 2 introduces the v2 schema)
# -----------------------------------------------------------------------------
warn "Skipping migrations: v2 schema lands in Phase 2."

# -----------------------------------------------------------------------------
# Done
# -----------------------------------------------------------------------------
echo ""
ok "Setup complete."
cat <<EOF

Next steps:
  - Review .env
  - Start everything:   ${GREEN}make dev${NC}
  - Or the API alone:   ${GREEN}make dev-api${NC}
  - Run tests:          ${GREEN}make test${NC}
EOF
