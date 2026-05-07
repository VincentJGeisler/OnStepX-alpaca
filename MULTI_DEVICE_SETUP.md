# OnStepX Multi-Device Setup

This driver runs three ASCOM Alpaca devices in a single process:
- Telescope (port 5555)
- Rotator (port 5556)  
- Focuser (port 5557)

## Configuration

Edit `device/config.toml`:

1. **Connection settings** (shared by all devices):
   - `connection_type`: 'serial' or 'tcp'
   - `serial_port`: Your OnStepX serial port
   - `tcp_host`, `tcp_port`: For WiFi OnStepX

2. **Telescope settings**:
   - `aperture_diameter`, `aperture_area`, `focal_length`: Your telescope optics
   - `position_poll_interval`: Position update frequency (seconds)

3. **Focuser settings**:
   - `focuser_number`: Which focuser (1-6) if you have multiple
   - `enable_temp_comp`: Temperature compensation on/off
   - `temp_comp_coefficient`: Microns per degree C

4. **Rotator settings**:
   - `enable_derotator`: Field rotation compensation

## Starting

```bash
./START_ALL_DEVICES.sh
```

Or manually:
```bash
cd device
python3 app.py
```

## Testing

```bash
# Telescope
curl http://localhost:5555/management/v1/description

# Rotator
curl http://localhost:5556/management/v1/description

# Focuser
curl http://localhost:5557/management/v1/description
```

## Stellarium/KStars

Add three separate devices:
- Type: Telescope, Host: localhost, Port: 5555
- Type: Rotator, Host: localhost, Port: 5556
- Type: Focuser, Host: localhost, Port: 5557
