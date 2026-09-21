#!/usr/bin/env bash
# Installs the storeyes device agent on a Raspberry Pi: the `at` scheduler (needed for
# longRunning commands), the agent files under /opt/storeyes-agent, its config, a cron.d entry
# that runs it every minute, a logrotate snippet so the log doesn't grow unbounded, and a
# sudoers rule letting the calling user (via storeyes-onboarding's POST /agent/run) trigger
# an immediate run instead of waiting for the next cron minute.
#
# Usage: sudo ./install.sh [--base-url https://panel.storeyes.io/api]
#
# Re-running this script (e.g. to ship a code update) never overwrites an existing config.conf.

set -euo pipefail

INSTALL_DIR="/opt/storeyes-agent"
CRON_FILE="/etc/cron.d/storeyes-agent"
LOGROTATE_FILE="/etc/logrotate.d/storeyes-agent"
LOG_FILE="/var/log/storeyes-agent.log"
BASE_URL="https://panel.storeyes.io/api"
SUDOERS_DST="/etc/sudoers.d/storeyes-agent-trigger"

if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root (sudo ./install.sh)" >&2
  exit 1
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing the 'at' scheduler (needed for long-running commands)..."
if ! command -v at >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y at
fi
systemctl enable --now atd

echo "Copying agent files to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR/main.py" "$SCRIPT_DIR/src" "$INSTALL_DIR/"

if [ ! -f "$INSTALL_DIR/config.conf" ]; then
  echo "Writing $INSTALL_DIR/config.conf (base_url=$BASE_URL)..."
  sed "s#^base_url = .*#base_url = $BASE_URL#" "$SCRIPT_DIR/config.conf.example" > "$INSTALL_DIR/config.conf"
else
  echo "Existing $INSTALL_DIR/config.conf left untouched."
fi

echo "Writing $CRON_FILE..."
cat > "$CRON_FILE" <<EOF
* * * * * root /usr/bin/python3 $INSTALL_DIR/main.py >> $LOG_FILE 2>&1
EOF
chmod 644 "$CRON_FILE"

echo "Writing $LOGROTATE_FILE..."
cat > "$LOGROTATE_FILE" <<EOF
$LOG_FILE {
  daily
  rotate 7
  compress
  missingok
  notifempty
}
EOF

if [ -n "${SUDO_USER:-}" ]; then
  echo "Installing the on-demand trigger sudoers rule for $SUDO_USER..."
  sed "s/^pi /$SUDO_USER /" "$SCRIPT_DIR/deploy/sudoers.d/storeyes-agent-trigger" > "$SUDOERS_DST"
  chmod 440 "$SUDOERS_DST"
  chown root:root "$SUDOERS_DST"
  visudo -cq || { echo "Generated sudoers file is invalid, removing it." >&2; rm -f "$SUDOERS_DST"; exit 1; }
  echo "$SUDO_USER can now run 'sudo /usr/bin/python3 $INSTALL_DIR/main.py' without a password"
  echo "(this is what storeyes-onboarding's POST /agent/run uses to trigger a run on demand)."
else
  echo "Skipping the on-demand trigger sudoers rule: could not determine the calling user (\$SUDO_USER unset)." >&2
  echo "Run this script via 'sudo ./install.sh' as that user, or add $SUDOERS_DST by hand — see deploy/sudoers.d/storeyes-agent-trigger." >&2
fi

BOARD_ID="$(python3 -c "import sys; sys.path.insert(0, '$INSTALL_DIR'); from src.device_identity import get_board_id; print(get_board_id())")"

echo ""
echo "Done. This device's serial (boardId) is: $BOARD_ID"
echo "Create or confirm a Device with this boardId in the admin panel."
