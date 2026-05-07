# OnStepX Alpaca Driver - Linux Setup Guide

Quick guide to get the OnStepX Alpaca driver running on Linux (Ubuntu, Debian, Fedora, Arch, Raspberry Pi, etc.).

---

## Prerequisites

### 1. Python 3.7 or later
Check your version:
```bash
python3 --version
```

If you need to install Python:

**Ubuntu/Debian/Raspberry Pi:**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

**Fedora:**
```bash
sudo dnf install python3 python3-pip
```

**Arch:**
```bash
sudo pacman -S python python-pip
```

### 2. Install Dependencies
```bash
cd /path/to/AlpycaDevice
pip3 install falcon pyserial
```

Or create a virtual environment (recommended):
```bash
cd /path/to/AlpycaDevice
python3 -m venv venv
source venv/bin/activate
pip install falcon pyserial
```

---

## Configuration

### 1. Find Your OnStepX Connection

**Option A: Serial/USB Connection**

List serial ports:
```bash
# Method 1: List all tty devices
ls /dev/tty*

# Method 2: Show USB serial devices only
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# Method 3: Use dmesg to see what was just plugged in
dmesg | grep tty

# Method 4: Detailed info
sudo lsusb
sudo dmesg | tail -20
```

Common device names:
- `/dev/ttyUSB0` - USB-to-serial adapters (FTDI, Prolific, etc.)
- `/dev/ttyACM0` - Arduino-based controllers
- `/dev/ttyAMA0` - Raspberry Pi GPIO serial
- `/dev/serial/by-id/*` - Persistent device names (recommended!)

**Tip:** Use persistent names to avoid port changes on reboot:
```bash
ls -l /dev/serial/by-id/
# Example: /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A50285BI-if00-port0
```

**Option B: WiFi/Network Connection**

Find your OnStepX IP address:
```bash
# Scan your network for OnStepX (port 9999)
nmap -p 9999 192.168.1.0/24

# Or use arp-scan
sudo arp-scan --localnet | grep -i "esp\|espressif"

# Or check DHCP leases
cat /var/lib/dhcp/dhcpd.leases | grep -i hostname
```

Default OnStepX WiFi port: **9999**

### 2. Set Up Serial Port Permissions

**Important:** Your user needs permission to access serial ports.

**Ubuntu/Debian/Raspberry Pi:**
```bash
# Add your user to dialout group
sudo usermod -a -G dialout $USER

# Log out and back in, or use:
newgrp dialout

# Verify you're in the group
groups
```

**Alternative (temporary, not recommended):**
```bash
sudo chmod 666 /dev/ttyUSB0
```

**Arch Linux:**
```bash
sudo usermod -a -G uucp $USER
newgrp uucp
```

### 3. Edit Configuration

Edit `device/config.toml`:

**For Serial/USB:**
```toml
[device]
connection_type = 'serial'
serial_port = '/dev/ttyUSB0'  # YOUR port here
# Or use persistent name:
# serial_port = '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A50285BI-if00-port0'
baud_rate = 9600
timeout = 2.0

# Leave these alone if using serial
tcp_host = '192.168.1.100'
tcp_port = 9999
```

**For WiFi/Network:**
```toml
[device]
connection_type = 'tcp'
tcp_host = '192.168.1.123'  # YOUR OnStepX IP here
tcp_port = 9999
timeout = 2.0

# Leave these alone if using TCP
serial_port = '/dev/ttyUSB0'
baud_rate = 9600
```

### 4. Configure Telescope Optics (Optional)

Edit the telescope parameters in `device/config.toml`:
```toml
aperture_diameter = 0.203  # meters (8 inch = 0.203m)
aperture_area = 0.032      # square meters
focal_length = 1.2         # meters
```

---

## Running the Driver

### Start the Server

```bash
cd /path/to/AlpycaDevice/device
python3 app.py
```

You should see:
```
[timestamp] INFO: OnStepX Alpaca Driver (Telescope) starting...
[timestamp] INFO: Listening on 0.0.0.0:5555
```

**The driver is now running!** Leave this terminal open.

### Test the Connection

Open a new terminal and test:

```bash
# Test discovery
curl http://localhost:5555/management/v1/description

# Should return JSON with driver info
```

If you see JSON output, the server is working!

---

## Testing with Your OnStepX

### 1. Connect to OnStepX

```bash
# Connect
curl -X PUT "http://localhost:5555/api/v1/telescope/0/connected" \
  -d "Connected=true&ClientID=1&ClientTransactionID=1"

# Should return: {"ClientTransactionID":1,"ServerTransactionID":1,"ErrorNumber":0,"ErrorMessage":""}
```

Watch the driver terminal for connection messages.

### 2. Check Position

```bash
# Get RA
curl "http://localhost:5555/api/v1/telescope/0/rightascension?ClientID=1&ClientTransactionID=2"

# Get Dec
curl "http://localhost:5555/api/v1/telescope/0/declination?ClientID=1&ClientTransactionID=3"

# Get tracking status
curl "http://localhost:5555/api/v1/telescope/0/tracking?ClientID=1&ClientTransactionID=4"
```

### 3. Test Tracking

```bash
# Enable tracking
curl -X PUT "http://localhost:5555/api/v1/telescope/0/tracking" \
  -d "Tracking=true&ClientID=1&ClientTransactionID=5"

# Disable tracking
curl -X PUT "http://localhost:5555/api/v1/telescope/0/tracking" \
  -d "Tracking=false&ClientID=1&ClientTransactionID=6"
```

---

## Using with Astronomy Software

### Stellarium (Recommended!)

**Install:**
```bash
# Ubuntu/Debian
sudo apt install stellarium

# Fedora
sudo dnf install stellarium

# Arch
sudo pacman -S stellarium

# Or download from https://stellarium.org/
```

**Configure:**
1. Start the Alpaca driver (see above)
2. Open Stellarium
3. Press `F2` or click Configuration (wrench icon)
4. Go to **Plugins** tab
5. Find **"Telescope Control"** and enable it
6. Click **Configure** button
7. Click **Add** → Choose **"ASCOM (Alpaca)"**
   - Name: OnStepX
   - Host: `localhost`
   - Port: `5555`
   - Device: `0`
8. Click **Connect**
9. Click on any object → `Ctrl+1` to slew!

### KStars/Ekos (Full Astrophotography Suite)

**Install:**
```bash
# Ubuntu/Debian
sudo apt install kstars-bleeding

# Fedora
sudo dnf install kstars

# Arch
sudo pacman -S kstars
```

**Configure:**
1. Open KStars
2. Tools → Ekos
3. Equipment Profile → Add new profile
4. Mount:
   - Driver: "Alpaca" (if available) or use INDI Alpaca bridge
   - Host: `localhost`
   - Port: `5555`

### CCDciel (Imaging)

```bash
# Download from https://www.ap-i.net/ccdciel/
# Supports Alpaca natively
```

### NINA via Wine (Windows astrophotography software)

```bash
# Install Wine
sudo apt install wine64

# Download NINA installer
# Some features may work, but native Linux software recommended
```

---

## Running as a System Service (systemd)

### Create Service File

Create `/etc/systemd/system/onstepx-alpaca.service`:

```ini
[Unit]
Description=OnStepX Alpaca Driver
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/AlpycaDevice/device
ExecStart=/usr/bin/python3 /path/to/AlpycaDevice/device/app.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# If using virtual environment, use this instead:
# ExecStart=/path/to/AlpycaDevice/venv/bin/python /path/to/AlpycaDevice/device/app.py

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable at boot
sudo systemctl enable onstepx-alpaca

# Start now
sudo systemctl start onstepx-alpaca

# Check status
sudo systemctl status onstepx-alpaca

# View logs
sudo journalctl -u onstepx-alpaca -f
```

**Control commands:**
```bash
sudo systemctl stop onstepx-alpaca     # Stop
sudo systemctl restart onstepx-alpaca  # Restart
sudo systemctl disable onstepx-alpaca  # Disable autostart
```

---

## Raspberry Pi Specific Setup

Perfect for dedicated observatory computer!

### Recommended: Raspberry Pi 4 (2GB+ RAM)

**1. Install Raspberry Pi OS Lite or Desktop**

**2. Update system:**
```bash
sudo apt update && sudo apt upgrade -y
```

**3. Install dependencies:**
```bash
sudo apt install python3 python3-pip python3-venv git
```

**4. Clone/copy the driver:**
```bash
cd ~
# If you have git access:
git clone <your-repo> AlpycaDevice
# Or use scp to copy from your Mac
```

**5. Install Python packages:**
```bash
cd ~/AlpycaDevice
python3 -m venv venv
source venv/bin/activate
pip install falcon pyserial
```

**6. Configure (see Configuration section above)**

**7. Set up as service** (see systemd section above)

**8. Enable WiFi** (if using wireless):
```bash
sudo raspi-config
# System Options → Wireless LAN
```

**9. Set static IP** (recommended for observatory):
Edit `/etc/dhcpcd.conf`:
```bash
interface eth0
static ip_address=192.168.1.200/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

**10. Access remotely:**
```bash
# From your Mac/PC:
ssh pi@192.168.1.200

# Or use the driver remotely:
# In Stellarium/KStars, use: 192.168.1.200:5555
```

---

## Troubleshooting

### "Permission denied" on serial port

```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Log out and back in, or:
newgrp dialout

# Verify
groups | grep dialout
```

### "Port already in use"

```bash
# Find what's using port 5555
sudo lsof -i :5555
sudo netstat -tlnp | grep 5555

# Kill it
sudo kill <PID>
```

### "Module not found"

```bash
# Install dependencies
pip3 install falcon pyserial

# Or if using venv:
source venv/bin/activate
pip install falcon pyserial
```

### Can't find OnStepX on network

```bash
# Scan for devices on port 9999
nmap -p 9999 192.168.1.0/24

# Check if you can ping it
ping 192.168.1.XXX

# Test direct connection
telnet 192.168.1.XXX 9999
# Type: :GVP#
# Should respond: On-Step#
```

### Serial port keeps changing (ttyUSB0 → ttyUSB1)

Use persistent device names:
```bash
# Find persistent name
ls -l /dev/serial/by-id/

# Use in config.toml:
serial_port = '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A50285BI-if00-port0'
```

### Firewall blocking connections

```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 5555/tcp

# Fedora/RHEL (firewalld)
sudo firewall-cmd --permanent --add-port=5555/tcp
sudo firewall-cmd --reload

# Check if firewall is running
sudo ufw status
# or
sudo firewall-cmd --list-all
```

### Test direct OnStepX connection

**Serial:**
```bash
# Install screen or minicom
sudo apt install screen

# Connect (9600 baud)
screen /dev/ttyUSB0 9600

# Type commands:
:GVP#         # Should return: On-Step#
:GVN#         # Version number
:GR#          # Right ascension

# Exit: Ctrl-A then K then Y
```

**TCP:**
```bash
telnet 192.168.1.123 9999
# Or use netcat:
nc 192.168.1.123 9999

# Type: :GVP#
# Should respond: On-Step#
```

### Driver crashes on startup

Check logs:
```bash
# If running as service:
sudo journalctl -u onstepx-alpaca -n 50

# If running manually:
# Look at terminal output
```

Common issues:
- Serial port name wrong
- Permission denied (see above)
- OnStepX not powered on
- Wrong baud rate (try 9600, 19200, 115200)
- Network firewall blocking port 9999

---

## Remote Observatory Setup

### VNC Setup (for desktop access)

```bash
# Install VNC server
sudo apt install tightvncserver

# Start VNC
vncserver :1

# Connect from remote:
# Use VNC client to connect to: 192.168.1.XXX:5901
```

### SSH Tunnel (secure remote access)

```bash
# On your local machine:
ssh -L 5555:localhost:5555 user@observatory-pi.local

# Now access http://localhost:5555 locally
# It tunnels to the remote Pi
```

### Tailscale VPN (easiest remote access)

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Connect
sudo tailscale up

# Access from anywhere via Tailscale IP
```

---

## Running Multiple Drivers

If you have multiple mounts or want OnStepX + rotator + focuser:

### Different ports:
```toml
# In each config.toml, use different ports:
# Mount:    port = 5555
# Focuser:  port = 5556
# Rotator:  port = 5557
```

Run each in separate directories or use separate config files.

---

## Performance Tips

### Raspberry Pi

```bash
# Disable unused services to save resources
sudo systemctl disable bluetooth
sudo systemctl disable cups

# Overclock (optional, Pi 4)
# Edit /boot/config.txt:
over_voltage=2
arm_freq=1800
```

### Reduce polling interval

Edit `config.toml`:
```toml
position_poll_interval = 0.5  # Slower = less CPU (but less responsive)
```

---

## Quick Start Script

Create `start-driver.sh`:
```bash
#!/bin/bash
cd /path/to/AlpycaDevice/device
source ../venv/bin/activate  # if using venv
python3 app.py
```

Make executable:
```bash
chmod +x start-driver.sh
```

Run:
```bash
./start-driver.sh
```

---

## Network Access from Other Devices

To use from Windows PC, tablet, etc. on same network:

1. Find your Linux machine's IP:
   ```bash
   hostname -I
   # or
   ip addr show | grep "inet "
   ```

2. Open firewall:
   ```bash
   sudo ufw allow 5555/tcp
   ```

3. In client software, use your Linux IP:
   ```
   http://192.168.1.XXX:5555
   ```

---

## Dedicated Observatory Computer Setup

**Recommended hardware:**
- Raspberry Pi 4 (4GB) or Intel NUC
- Powered USB hub for mount + cameras
- SSD instead of SD card (reliability)
- UPS for power protection

**Software stack:**
```
┌─────────────────────────────────────┐
│  Stellarium / KStars / NINA         │  ← Remote control from laptop/tablet
└──────────────┬──────────────────────┘
               │ Network (WiFi/Ethernet)
┌──────────────┴──────────────────────┐
│  OnStepX Alpaca Driver (Port 5555)  │  ← Running on Pi/NUC
│  + INDI server (other devices)      │
└──────────────┬──────────────────────┘
               │ USB Serial / TCP
┌──────────────┴──────────────────────┐
│  OnStepX Mount Controller           │
└─────────────────────────────────────┘
```

**Auto-start on boot:**
1. Use systemd service (see above)
2. Set static IP
3. Enable SSH
4. Set up VNC or remote desktop
5. Configure firewall

---

## Next Steps

1. ✅ Start the driver
2. ✅ Test connection with curl commands
3. ✅ Install Stellarium
4. ✅ Connect from Stellarium
5. 📸 Test basic operations (slew, track, park)
6. 🔍 Run extended tests with your mount
7. 🌐 Set up remote access if needed
8. 📋 Report any issues or bugs

---

## Support

- GitHub Issues: https://github.com/ASCOMInitiative/AlpycaDevice/issues
- ASCOM Forum: https://ascomtalk.groups.io/g/Developer
- OnStepX Forum: https://groups.io/g/onstep
- KStars/Ekos: https://invent.kde.org/education/kstars

---

## Logs Location

- **Manual run:** Terminal output
- **systemd service:** `sudo journalctl -u onstepx-alpaca -f`
- **Application log:** Check `device/` directory for log files if configured
