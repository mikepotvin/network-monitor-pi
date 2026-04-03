# Network Monitor for Raspberry Pi

A lightweight, always-on network monitor that tracks packet loss, disconnects, latency, jitter, DNS/HTTP health, and nightly speed tests. View everything via a web dashboard from any device on your network.

## Features

- **Ping monitoring** — Pings gateway + 3 external DNS servers every second
- **DNS & HTTP checks** — Tests DNS resolution and HTTP reachability every 60 seconds
- **Nightly speed tests** — Runs at 1:00 AM via speedtest-cli
- **Outage detection** — Logs outages with start/end times, duration, and error messages
- **Web dashboard** — Dark-themed, responsive, works on phone/tablet/desktop
- **Auto-start** — Runs as a systemd service, survives reboots
- **Low resource** — ~50 MB RAM, ~50-80 MB storage for 30 days of data

## Requirements

- Raspberry Pi 3 (or newer) with Raspberry Pi OS Lite (64-bit)
- Ethernet connection to your router
- Python 3.11+

## Quick Setup

1. **Flash Raspberry Pi OS Lite (64-bit)** using [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
   - Set hostname to `networkmon`
   - Enable SSH
   - Set username and password
   - Set timezone

2. **Connect Pi via ethernet** and SSH in:
   ```bash
   ssh your-user@networkmon.local
   ```

3. **Update the system:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y python3-venv git
   ```

4. **Clone and install:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/network-monitor-pi.git
   cd network-monitor-pi
   sudo bash setup.sh
   ```

5. **Open the dashboard** at `http://networkmon.local:5000`

## Managing the Service

```bash
# Check status
sudo systemctl status network-monitor

# View live logs
sudo journalctl -u network-monitor -f

# Restart
sudo systemctl restart network-monitor

# Stop
sudo systemctl stop network-monitor
```

## Updating

Full update (new dependencies, service file changes, or first time after adding features):

```bash
cd ~/network-monitor-pi   # wherever you cloned the repo
git pull
sudo bash setup.sh        # copies files to /opt, installs deps, restarts service
```

Quick update (Python/frontend code only, no new dependencies):

```bash
cd ~/network-monitor-pi
git pull
sudo cp -r src static templates /opt/network-monitor/
sudo systemctl restart network-monitor
```

## Development

```bash
# Set up dev environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Run tests
pytest -v

# Run locally (monitoring requires cap_net_raw or root)
MONITOR_NO_SCHEDULER=1 flask --app src.web run --debug
```

## Architecture

Single Python process: Flask serves the web dashboard while a background thread handles all monitoring. Results buffer in memory and flush to SQLite every 30 seconds.

```
Browser ──→ Flask (port 5000) ──→ SQLite ←── Monitor Thread
                                              ├── Ping (1s)
                                              ├── DNS (60s)
                                              ├── HTTP (60s)
                                              └── Speed Test (1AM)
```
