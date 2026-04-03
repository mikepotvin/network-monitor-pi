#!/usr/bin/env bash
set -euo pipefail

# Network Monitor - Raspberry Pi Setup Script
# Run as root: sudo bash setup.sh

INSTALL_DIR="/opt/network-monitor"
SERVICE_NAME="network-monitor"
SERVICE_USER="networkmon"

echo "=== Network Monitor Setup ==="

# Check for root
if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo bash setup.sh)"
    exit 1
fi

# Create system user
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating system user: $SERVICE_USER"
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# Grant journal read access for the log viewer dashboard
usermod -aG systemd-journal "$SERVICE_USER"

# Create install directory
echo "Setting up $INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"

# Copy application files
cp -r src static templates requirements.txt "$INSTALL_DIR/"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Create virtual environment
echo "Creating Python virtual environment"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# Set raw socket capability for ICMP pings without root
echo "Setting network capabilities"
PYTHON_BIN="$INSTALL_DIR/venv/bin/python3"
# Resolve symlink to actual binary
PYTHON_REAL=$(readlink -f "$PYTHON_BIN")
setcap cap_net_raw+ep "$PYTHON_REAL"

# Install systemd service
echo "Installing systemd service"
cp network-monitor.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo ""
echo "=== Setup Complete ==="
echo "Service status: systemctl status $SERVICE_NAME"
echo "View logs:      journalctl -u $SERVICE_NAME -f"
echo "Dashboard:      http://$(hostname -I | awk '{print $1}'):5000"
