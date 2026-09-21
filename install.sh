#!/usr/bin/env bash
# Installs the storeyes device agent on a Raspberry Pi: the `at` scheduler (needed for
# longRunning commands), its config, a cron.d entry that runs it every minute, and a logrotate
# snippet so the log doesn't grow unbounded. The agent runs from wherever this script lives —
# nothing is copied elsewhere, so a `git pull` in this directory is all a code update takes.
#
# The agent runs as root (cron.d), but with HOME and its working directory set to base_dir
# (/home/m0hcine24 by default) so that installs — and any command using `~` — land in the real
# user's home rather than /root.
#
# Usage: sudo ./install.sh [--base-url https://panel.storeyes.io/api] [--base-dir /home/m0hcine24]
#
# Re-running this script (e.g. after a code update) never overwrites an existing config.conf.

set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_FILE="/etc/cron.d/storeyes-agent"
LOGROTATE_FILE="/etc/logrotate.d/storeyes-agent"
LOG_FILE="/var/log/storeyes-agent.log"
BASE_URL="https://panel.storeyes.io/api"
BASE_DIR="/home/m0hcine24"

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
    --base-dir)
      BASE_DIR="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

echo "Installing the 'at' scheduler (needed for long-running commands)..."
if ! command -v at >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y at
fi
systemctl enable --now atd

echo "Running the agent in place from $INSTALL_DIR (nothing is copied)."

if [ ! -f "$INSTALL_DIR/config.conf" ]; then
  echo "Writing $INSTALL_DIR/config.conf (base_url=$BASE_URL, base_dir=$BASE_DIR)..."
  sed "s#^base_url = .*#base_url = $BASE_URL#; s#^base_dir = .*#base_dir = $BASE_DIR#" "$INSTALL_DIR/config.conf.example" > "$INSTALL_DIR/config.conf"
else
  echo "Existing $INSTALL_DIR/config.conf left untouched."
fi

# Read base_dir back out of the config that's actually in place, so the cron entry's HOME can't
# drift from what the agent itself will use (an existing config.conf wins over --base-dir).
BASE_DIR="$(python3 -c "import sys; sys.path.insert(0, '$INSTALL_DIR'); from src.config import load_config; print(load_config().base_dir)")"

if [ ! -d "$BASE_DIR" ]; then
  echo "Warning: base_dir $BASE_DIR does not exist — INSTALL commands will fail until it does." >&2
fi

# Runs as root, but with HOME=base_dir: the agent chdirs into base_dir per command itself (see
# src/executor.py), and this keeps anything reading HOME earlier than that off /root too. It's
# set here rather than with a `cd` in the command so a missing base_dir can't stop the poll loop
# entirely — individual commands then fail and get reported to the panel, which is easier to see.
echo "Writing $CRON_FILE..."
cat > "$CRON_FILE" <<EOF
HOME=$BASE_DIR
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

BOARD_ID="$(python3 -c "import sys; sys.path.insert(0, '$INSTALL_DIR'); from src.device_identity import get_board_id; print(get_board_id())")"

echo ""
echo "Done. Running as root from $INSTALL_DIR, with base_dir $BASE_DIR."
echo "This device's serial (boardId) is: $BOARD_ID"
echo "Create or confirm a Device with this boardId in the admin panel."
