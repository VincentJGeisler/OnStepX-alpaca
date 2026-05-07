# OnStepX Rotator & Focuser Implementation Plan

## Overview
Add ASCOM Rotator and Focuser device support to the existing OnStepX Alpaca driver. These will run as additional devices on separate ports alongside the telescope.

---

## Architecture

### Multi-Device Structure
```
http://localhost:5555/api/v1/telescope/0/...   (existing)
http://localhost:5556/api/v1/rotator/0/...     (NEW)
http://localhost:5557/api/v1/focuser/0/...     (NEW)
```

Each device runs as a separate Alpaca server instance with its own port.

---

## Phase 1: Rotator Implementation

### 1.1 OnStepX Rotator Commands (from COMMANDS.md lines 718-826)

**Status/Info:**
- `:rA#` - Check if rotator active (returns 1/0)
- `:rT#` - Get rotator status
- `:rG#` - Get current angle (sDDD*MM# or sDDD*MM:SS#)
- `:rI#` - Get minimum position (degrees)
- `:rM#` - Get maximum position (degrees)
- `:rD#` - Get degrees per step
- `:rb#` - Get backlash (steps)
- `:rW#` - Get working slew rate (deg/s)
- `:GX98#` - Get rotator availability

**Movement:**
- `:rS[sDDD*MM]#` - Set target angle (absolute)
- `:rr[sDDD*MM]#` - Set target angle (relative move)
- `:r>#` - Move clockwise
- `:r<#` - Move counter-clockwise
- `:rQ#` - Stop rotator movement

**Positioning:**
- `:rZ#` - Set position to zero
- `:rF#` - Set position to half-travel
- `:rC#` - Move to half-travel position

**Park:**
- `:hP#` - Park rotator (NOTE: same as telescope park!)
- `:hR#` - Unpark rotator (NOTE: same as telescope unpark!)

**Configuration:**
- `:rb[n]#` - Set backlash (steps)
- `:r[n]#` - Set move/goto rate
- `:rc#` - Set continuous move mode

**Derotator (field rotation compensation):**
- `:r+#` - Enable derotator
- `:r-#` - Disable derotator
- `:rR#` - Reverse derotator direction
- `:rP#` - Move to parallactic angle

### 1.2 Files to Create

**device/onstepx_rotator.py** (NEW)
- Reuse OnStepXDevice connection from telescope
- Add rotator-specific command methods:
  - `get_position() -> float` (degrees)
  - `get_is_moving() -> bool`
  - `move_absolute(angle: float)`
  - `move_relative(offset: float)`
  - `halt()`
  - `get_mechanical_position() -> float`
  - `sync(angle: float)` - via `:rZ#` then set
  - `get_step_size() -> float` - via `:rD#`
  - `get_can_reverse() -> bool` - True (has `:rR#`)
  - `get_reverse() -> bool` - check derotator state
  - `set_reverse(value: bool)` - via `:rR#`

**device/rotatordevice.py** (REPLACE existing simulator)
- Delete simulation code
- Wrap onstepx_rotator with ASCOM IRotatorV4 interface
- Properties:
  - `position` (GET) - mechanical position 0-360°
  - `mechanical_position` (GET) - raw position
  - `is_moving` (GET) - check via status
  - `can_reverse` (GET) - True
  - `reverse` (GET/PUT) - derotator direction
  - `step_size` (GET) - degrees per step
  - `target_position` (GET/PUT) - target angle
- Methods:
  - `move(position: float)` - RELATIVE move via `:rr#` (IRotatorV4 spec)
  - `move_absolute(position: float)` - ABSOLUTE move via `:rS#`
  - `move_mechanical(position: float)` - absolute move, no sync offset
  - `halt()` - via `:rQ#`
  - `sync(position: float)` - software offset (`:rZ#` only sets zero, maintain offset like simulator)

**device/rotator.py** (MODIFY existing)
- Update RotatorMetadata:
  ```python
  Name = 'OnStepX Rotator'
  Version = '1.0.0'
  Description = 'ASCOM Alpaca Rotator for OnStepX Controller'
  DeviceID = '<NEW GUID>'
  ```
- Update device initialization to use OnStepX backend
- Implement all responder GET/PUT methods (already scaffolded)
- Remove simulator placeholders

**device/rotator_app.py** (NEW)
- Copy app.py structure
- Change port to 5556
- Import rotator module
- Initialize rotator device
- Route rotator endpoints

**device/rotator_config.toml** (NEW)
```toml
title = "OnStepX Alpaca Driver (Rotator)"

[network]
ip_address = ''
port = 5556

[server]
location = 'Your Observatory'
verbose_driver_exceptions = true

[device]
# Share connection settings with telescope
connection_type = 'serial'  # or 'tcp'
serial_port = '/dev/ttyUSB0'
tcp_host = '192.168.1.100'
tcp_port = 9999
baud_rate = 9600
timeout = 2.0
# Rotator specific
enable_derotator = false    # Field rotation compensation

[logging]
log_level = 'INFO'
log_to_stdout = true
max_size_mb = 5
num_keep_logs = 10
```

### 1.3 Key Design Decisions

**Connection Sharing:**
- Rotator shares the same serial/TCP connection as telescope
- OnStepX multiplexes commands on one connection
- Use shared OnStepXDevice instance with locking

**Position Sync:**
- IRotator requires 0-360° mechanical position
- OnStepX `:rG#` returns signed angle
- Normalize to 0-360° range
- Support sync offset for mechanical vs sky position

**Reverse:**
- Maps to derotator reverse (`:rR#`)
- Not true mechanical reverse, but matches intent

**Moving State:**
- Poll `:rT#` status or track after move commands
- No explicit "is moving" command, derive from state

---

## Phase 2: Focuser Implementation

### 2.1 OnStepX Focuser Commands (from COMMANDS.md lines 828-949)

**Status/Info:**
- `:FA#` - Check if focuser active (returns 1/0)
- `:FA[n]#` - Select focuser (1-6)
- `:Fa#` - Get primary focuser number
- `:FT#` - Get focuser status
- `:FG#` - Get current position (microns or steps)
- `:FI#` - Get full-in position
- `:FM#` - Get maximum position
- `:Fp#` - Get focuser mode
- `:Fu#` - Get microns per step

**Movement:**
- `:FS[n]#` - Set target position
- `:FG#` - Goto target position (NOTE: conflicts with get position!)
- `:F+#` - Move in (toward telescope)
- `:F-#` - Move out (away from telescope)
- `:FF#` - Move to full-in position
- `:FQ#` - Stop focuser
- `:FZ#` - Set current position as zero

**Temperature Compensation:**
- `:Ft#` - Get focuser temperature (°C)
- `:Fe#` - Get temperature differential (°C)
- `:FC#` - Get compensation coefficient (microns/°C)
- `:FC[sn.n]#` - Set compensation coefficient
- `:Fc#` - Get compensation enable status
- `:Fc[n]#` - Enable/disable compensation
- `:FD#` - Get compensation deadband
- `:FD[n]#` - Set compensation deadband

**Configuration:**
- `:FB#` - Get backlash
- `:FB[n]#` - Set backlash
- `:FP#` - Get DC motor power level (percent)
- `:FP[n]#` - Set DC motor power level

### 2.2 Files to Create

**device/onstepx_focuser.py** (NEW)
- Reuse OnStepXDevice connection
- Add focuser-specific command methods:
  - `get_position() -> int` (microns or steps)
  - `get_is_moving() -> bool`
  - `move_absolute(position: int)`
  - `move_relative(offset: int)` - calculate target
  - `halt()`
  - `get_max_position() -> int`
  - `get_max_increment() -> int` - max single move
  - `get_temperature() -> float`
  - `get_temp_comp() -> bool`
  - `set_temp_comp(enabled: bool)`
  - `get_temp_comp_coefficient() -> float`
  - `set_temp_comp_coefficient(value: float)`
  - `select_focuser(number: int)` - for multi-focuser support

**device/focuserdevice.py** (NEW)
- Wrap onstepx_focuser with ASCOM IFocuserV4 interface
- Properties:
  - `absolute` (GET) - True (OnStepX uses absolute positioning)
  - `position` (GET) - current position
  - `is_moving` (GET) - check via `:FT#` status
  - `max_increment` (GET) - from `:FM#` or config
  - `max_step` (GET) - from `:FM#`
  - `step_size` (GET) - from `:Fu#`
  - `temp_comp` (GET/PUT) - temperature compensation via `:Fc#`/`:Fc[n]#`
  - `temp_comp_available` (GET) - True if `:Ft#` returns temp
  - `temperature` (GET) - from `:Ft#`
- Methods:
  - `move(position: int)` - absolute move via `:FS#` then `:FG#`
  - `halt()` - via `:FQ#`

**device/focuser.py** (NEW - from template)
- Copy from templates/focuser.py
- Update FocuserMetadata:
  ```python
  Name = 'OnStepX Focuser'
  Version = '1.0.0'
  Description = 'ASCOM Alpaca Focuser for OnStepX Controller'
  DeviceID = '<NEW GUID>'
  InterfaceVersion = 4
  ```
- Implement all responders
- Import focuserdevice

**device/focuser_app.py** (NEW)
- Copy app.py structure
- Change port to 5557
- Import focuser module
- Initialize focuser device
- Route focuser endpoints

**device/focuser_config.toml** (NEW)
```toml
title = "OnStepX Alpaca Driver (Focuser)"

[network]
ip_address = ''
port = 5557

[server]
location = 'Your Observatory'
verbose_driver_exceptions = true

[device]
# Share connection settings
connection_type = 'serial'
serial_port = '/dev/ttyUSB0'
tcp_host = '192.168.1.100'
tcp_port = 9999
baud_rate = 9600
timeout = 2.0
# Focuser specific
focuser_number = 1          # Which focuser (1-6)
enable_temp_comp = true     # Temperature compensation
temp_comp_coefficient = 5.0 # Microns per °C

[logging]
log_level = 'INFO'
log_to_stdout = true
max_size_mb = 5
num_keep_logs = 10
```

### 2.3 Key Design Decisions

**Command Conflict:**
- `:FG#` means BOTH "get position" AND "goto target"
- Resolution: Use context - after `:FS#` it means goto, otherwise get
- Better: Always use `:FG#` immediately after `:FS#` for moves

**Position Units:**
- OnStepX uses microns OR steps depending on mode
- Query `:Fp#` to determine mode
- ASCOM Focuser uses integer position (unit agnostic)
- Pass through OnStepX units directly

**Temperature Compensation:**
- Full support via OnStepX commands
- Coefficient: positive = move out as temperature falls
- Deadband prevents hunting

**Multi-Focuser:**
- OnStepX supports 6 focusers via `:FA[n]#`
- Config specifies which focuser (default 1)
- Send select command on connect

---

## Phase 3: Integration & Configuration

### 3.1 Connection Sharing Strategy

**CRITICAL ARCHITECTURE DECISION (Updated after Opus review):**

**Option A (REJECTED): Separate processes with singleton**
- Would require IPC (inter-process communication) for shared connection
- Overly complex

**Option B (SELECTED): Single process, multiple WSGI servers**
- One Python process runs app.py
- Spawns three WSGI servers on ports 5555, 5556, 5557
- One shared OnStepXDevice instance with existing locking
- Telescope, rotator, focuser modules all import same instance
- Pros: Simple, thread-safe via existing lock, proven pattern
- Cons: All devices stop if process crashes (acceptable)

**Implementation:**
- Modify app.py to spawn three wsgiref servers (one per device type)
- Each server routes to its device module (telescope/rotator/focuser)
- Shared OnStepXDevice instance initialized once, passed to all three
- Existing `threading.Lock` in `send_command()` serializes access

### 3.2 Startup Scripts

**start-all.sh:**
```bash
#!/bin/bash
cd /path/to/AlpycaDevice/device
python3 app.py  # Runs all three devices (telescope, rotator, focuser) on ports 5555-5557
```

**systemd service:**
- `onstepx-alpaca.service` - Single service runs all three devices
- Simpler management, all devices start/stop together

### 3.3 Discovery

Update management endpoints to advertise all three devices:
- Telescope: `http://localhost:5555/management/v1/description`
- Rotator: `http://localhost:5556/management/v1/description`
- Focuser: `http://localhost:5557/management/v1/description`

---

## Phase 4: Testing

### Rotator Tests
```bash
# Check availability
curl http://localhost:5556/management/v1/description

# Connect
curl -X PUT http://localhost:5556/api/v1/rotator/0/connected -d "Connected=true&ClientID=1"

# Get position
curl "http://localhost:5556/api/v1/rotator/0/position?ClientID=1&ClientTransactionID=1"

# Move to 180°
curl -X PUT http://localhost:5556/api/v1/rotator/0/moveabsolute -d "Position=180&ClientID=1&ClientTransactionID=2"

# Check moving
curl "http://localhost:5556/api/v1/rotator/0/ismoving?ClientID=1&ClientTransactionID=3"
```

### Focuser Tests
```bash
# Check availability
curl http://localhost:5557/management/v1/description

# Connect
curl -X PUT http://localhost:5557/api/v1/focuser/0/connected -d "Connected=true&ClientID=1"

# Get position
curl "http://localhost:5557/api/v1/focuser/0/position?ClientID=1&ClientTransactionID=1"

# Move to position 5000
curl -X PUT http://localhost:5557/api/v1/focuser/0/move -d "Position=5000&ClientID=1&ClientTransactionID=2"

# Get temperature
curl "http://localhost:5557/api/v1/focuser/0/temperature?ClientID=1&ClientTransactionID=3"

# Enable temp comp
curl -X PUT http://localhost:5557/api/v1/focuser/0/tempcomp -d "TempComp=true&ClientID=1&ClientTransactionID=4"
```

---

## Implementation Order

1. ✅ **Review this plan with Opus**
2. **Rotator (Haiku):**
   - onstepx_rotator.py
   - Update rotatordevice.py
   - Update rotator.py responders
   - rotator_app.py
   - rotator_config.toml
3. **Focuser (Haiku):**
   - onstepx_focuser.py
   - focuserdevice.py
   - focuser.py responders
   - focuser_app.py
   - focuser_config.toml
4. **Integration (Haiku):**
   - Shared connection module
   - Startup scripts
   - Update documentation
5. **Testing:**
   - Unit tests for commands
   - Integration tests with hardware
   - ConformU validation

---

## Known Limitations

1. **Park commands conflict:** `:hP#`/`:hR#` used by both telescope and rotator - need to clarify OnStepX behavior
2. **`:FG#` command overload:** Means both get position and goto - handle with care
3. **Connection sharing:** Serial connection must be carefully arbitrated
4. **Derotator limitations:** OnStepX derotator is field rotation compensation, not true reverse

---

## Documentation Updates Needed

- MACOS_SETUP.md - Add rotator/focuser sections
- LINUX_SETUP.md - Add rotator/focuser sections
- COMPLETION_REPORT.md - Update with new devices
- Create ROTATOR_FOCUSER_SETUP.md - Dedicated guide

---

## Dependencies

No new dependencies - reuse existing:
- falcon (REST API)
- pyserial (serial/TCP communication)
- Python 3.7+ standard library
