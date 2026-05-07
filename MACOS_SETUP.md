# OnStepX Alpaca Driver - macOS Setup Guide

Quick guide to get the OnStepX Alpaca driver running on macOS.

---

## Prerequisites

### 1. Python 3.7 or later
Check your version:
```bash
python3 --version
```

If you need to install Python:
```bash
brew install python3
```

### 2. Install Dependencies
```bash
cd /Users/vince/src/AlpycaDevice
pip3 install falcon pyserial
```

Or create a virtual environment (recommended):
```bash
cd /Users/vince/src/AlpycaDevice
python3 -m venv venv
source venv/bin/activate
pip install falcon pyserial
```

---

## Configuration

### 1. Find Your OnStepX Connection

**Option A: Serial/USB Connection**
```bash
# List serial ports
ls /dev/tty.*
```

Look for something like:
- `/dev/tty.usbserial-*` (FTDI adapters)
- `/dev/tty.usbmodem*` (Arduino-based controllers)
- `/dev/tty.SLAB_USBtoUART` (Silicon Labs adapters)

**Option B: WiFi/Network Connection**

Find your OnStepX IP address:
- Check your SWS (Smart Web Server) - usually shows at top
- Check your router's DHCP client list
- Use network scanner: `arp -a` or Angry IP Scanner app

Default OnStepX port is usually **9999**.

### 2. Edit Configuration

Edit `device/config.toml`:

**For Serial/USB:**
```toml
[device]
connection_type = 'serial'
serial_port = '/dev/tty.usbserial-AB0KXYZ'  # YOUR port here
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

### 3. Configure Telescope Optics (Optional)

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
cd /Users/vince/src/AlpycaDevice/device
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

### KStars/Ekos (macOS)

1. Open KStars
2. Go to Tools → Ekos
3. Click "+" to add equipment profile
4. For Mount:
   - Driver: "INDI Alpaca" or use generic Alpaca driver
   - Host: `localhost`
   - Port: `5555`

### SkySafari (iPad/iPhone on same WiFi)

1. Open SkySafari
2. Settings → Telescope
3. Setup: "Other"
4. Mount Type: "Alpaca"
5. IP Address: Your Mac's IP (not localhost!)
   ```bash
   # Find your Mac's IP:
   ifconfig | grep "inet " | grep -v 127.0.0.1
   ```
6. Port: `5555`
7. Connect

### Cartes du Ciel (macOS)

1. Setup → Telescope → ASCOM
2. Select "Alpaca Discovery"
3. Should find "OnStepX Telescope" at `localhost:5555`
4. Select it and connect

### NINA (via Windows VM or Wine)

1. Equipment → Telescope
2. Add ASCOM Alpaca device
3. Discovery should find the driver
4. Or manually: `http://YOUR_MAC_IP:5555`

---

## Troubleshooting

### "Permission denied" on serial port

macOS may need permissions:
```bash
# Add your user to dialout group (if exists)
sudo dseditgroup -o edit -a $USER -t user dialout

# Or change port permissions (temporary)
sudo chmod 666 /dev/tty.usbserial-*

# Reboot may be needed
```

### "Connection refused"

Check firewall:
```bash
# Allow incoming connections on port 5555
System Preferences → Security & Privacy → Firewall → Firewall Options
→ Allow Python (or add it)
```

### "Module not found"

Dependencies not installed:
```bash
pip3 install falcon pyserial
# or if using venv:
source venv/bin/activate
pip install falcon pyserial
```

### Can't find OnStepX IP address

```bash
# Ping common subnet
ping 192.168.1.1

# Or use network scanner
brew install nmap
nmap -p 9999 192.168.1.0/24
```

### Driver crashes on startup

Check logs in terminal. Common issues:
- Serial port name wrong (check `ls /dev/tty.*`)
- OnStepX not powered on
- Wrong baud rate (try 9600, 19200, 115200)
- TCP port blocked by firewall

### Test direct OnStepX connection

Serial:
```bash
screen /dev/tty.usbserial-* 9600
# Type: :GVP#
# Should respond: On-Step#
# Exit: Ctrl-A then K
```

TCP:
```bash
telnet 192.168.1.123 9999
# Type: :GVP#
# Should respond: On-Step#
# Exit: Ctrl-] then quit
```

---

## Running as a Background Service (Optional)

### Using launchd (macOS native)

Create `~/Library/LaunchAgents/com.onstepx.alpaca.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.onstepx.alpaca</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/vince/src/AlpycaDevice/device/app.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/vince/src/AlpycaDevice/device</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/onstepx-alpaca.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/onstepx-alpaca.error.log</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.onstepx.alpaca.plist
```

Stop it:
```bash
launchctl unload ~/Library/LaunchAgents/com.onstepx.alpaca.plist
```

Check logs:
```bash
tail -f /tmp/onstepx-alpaca.log
```

### Using screen (simpler)

```bash
# Start in background
screen -dmS onstepx python3 /Users/vince/src/AlpycaDevice/device/app.py

# Reattach to see output
screen -r onstepx

# Detach: Ctrl-A then D

# Kill it
screen -X -S onstepx quit
```

---

## Quick Start Script

Create `start-driver.sh`:
```bash
#!/bin/bash
cd /Users/vince/src/AlpycaDevice/device
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

To use from iPad, Windows PC, etc. on same network:

1. Find your Mac's IP:
   ```bash
   ifconfig en0 | grep "inet " | awk '{print $2}'
   ```

2. Allow firewall (if enabled):
   ```
   System Preferences → Security & Privacy → Firewall
   → Firewall Options → Add Python → Allow incoming connections
   ```

3. In client software, use your Mac's IP instead of localhost:
   ```
   http://192.168.1.XXX:5555
   ```

---

## Remote Observatory Setup

If your Mac is connected to OnStepX at an observatory:

1. **SSH into Mac:**
   ```bash
   ssh you@your-mac.local
   cd /Users/vince/src/AlpycaDevice/device
   screen -dmS onstepx python3 app.py
   ```

2. **SSH tunnel** (if Mac firewall blocks external access):
   ```bash
   # On remote machine:
   ssh -L 5555:localhost:5555 you@your-mac.local
   
   # Now access http://localhost:5555 on remote machine
   ```

3. **VPN** (recommended for security):
   - Set up VPN to observatory network
   - Access Mac directly via local IP

---

## Next Steps

1. ✅ Start the driver
2. ✅ Test connection with curl commands
3. ✅ Connect from astronomy software
4. 📸 Test basic operations (slew, track, park)
5. 🔍 Run extended tests with your mount
6. 📋 Report any issues or bugs

---

## Support

- GitHub Issues: https://github.com/ASCOMInitiative/AlpycaDevice/issues
- ASCOM Forum: https://ascomtalk.groups.io/g/Developer
- OnStepX Forum: https://groups.io/g/onstep

Logs location: Check terminal output or `/tmp/onstepx-alpaca.log` if using launchd
