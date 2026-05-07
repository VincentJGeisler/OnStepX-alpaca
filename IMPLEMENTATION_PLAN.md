# OnStepX Alpaca Driver - Implementation Plan

## Overview
Create a complete ASCOM Alpaca driver for OnStepX telescope controller using the AlpycaDevice SDK boilerplate. The driver will expose OnStepX as an ASCOM-compliant telescope device via the Alpaca REST API.

## Architecture

### Component Structure
```
device/
├── app.py                    # Main application (modify to import telescope)
├── config.toml              # Configuration (serial port, baud rate, OnStepX settings)
├── onstepx_device.py        # NEW: Low-level OnStepX serial communication
├── telescopedevice.py       # NEW: Telescope device logic layer
├── telescope.py             # NEW: Alpaca API responders (Falcon endpoints)
├── shr.py                   # Shared utilities (already exists)
├── exceptions.py            # ASCOM exceptions (already exists)
└── log.py                   # Logging (already exists)
```

## Critical Design Updates (From Opus Review)

1. **Use `:Gm#` for pier side** - Primary method, returns E#/W#/N# directly
2. **Leverage `:GU#` status command** - Single command for combined state (tracking, parking, slewing, at-home)
3. **Use `:CM#` for sync operations** - Set target first (`:Sr#`/`:Sd#`), then call `:CM#`
4. **Update `management.py`** - Must import TelescopeMetadata for Alpaca discovery
5. **Longitude sign inversion** - OnStepX east-negative, ASCOM east-positive (must negate!)
6. **Track `IsPulseGuiding` state** - Timer-based tracking of pulse guide duration
7. **Map rate offset commands** - `:GXTR#`/`:SXTR#` for RA, `:GXTD#`/`:SXTD#` for Dec
8. **Connection validation** - Use `:GVP#` on connect, validate response contains "On-Step"
9. **Support WiFi/TCP** - Abstract connection layer for serial + TCP (ESP8266/ESP32)
10. **Background polling thread** - Cache position/status with configurable interval (250ms recommended)

## Phase 1: Core Telescope Implementation

### 1.1 OnStepX Communication Module (`onstepx_device.py`)

**Purpose:** Handle all serial communication with OnStepX hardware.

**Key Features:**
- Serial port connection management (pySerial)
- Command sending with proper formatting (`:CMD#` pattern)
- Response parsing and validation
- Command queue management to prevent conflicts
- Thread-safe operations with locking
- Error detection and retry logic
- Connection state tracking

**Critical Commands to Implement:**
- **Connection/Info:** `:GVN#` (version), `:GVP#` (product - validate "On-Step"), `:GVM#` (message)
- **Position Reading:** `:GR#`, `:GD#`, `:GA#`, `:GZ#` (RA/Dec/Alt/Az)
- **High Precision:** `:GRH#`, `:GDH#`, `:GAH#`, `:GZH#`
- **Target Setting:** `:Sr[RA]#`, `:Sd[Dec]#`, `:Sa[Alt]#`, `:Sz[Az]#`
- **Goto:** `:MS#` (equatorial), `:MA#` (alt/az)
- **Movement:** `:Mn#/:Ms#/:Me#/:Mw#` (N/S/E/W), `:Q#` (stop)
- **Tracking:** `:T+#/:T-#`, `:GT#`, `:TQ#/:TL#/:TS#/:TK#`
- **Tracking Rates:** `:GXTR#/:SXTR,n.n#` (RA offset), `:GXTD#/:SXTD,n.n#` (Dec offset)
- **Park/Home:** `:hP#`, `:hR#`, `:hC#`, `:hF#` (set home after cold start)
- **Site:** `:Gt#/:St#`, `:Gg#/:Sg#`, `:Gv#/:Sv#` (lat/lon/elevation - **NOTE:** OnStepX east-negative, ASCOM east-positive)
- **Time:** `:GS#/:SL#/:SC#/:SG#` (sidereal/local/date/UTC offset)
- **Limits:** `:Gh#/:Sh#`, `:Go#/:So#`
- **Status:** `:D#` (is moving), `:GU#` (combined status - **CRITICAL for efficiency**)
- **Alignment:** `:A[n]#`, `:A+#`, `:CM#` (sync to target - use this for SyncToCoordinates/SyncToTarget)
- **Guiding:** `:Mgd[n]#`, `:Mgr[n]#`, `:RG#/:RC#/:RM#/:RF#/:RS#`
- **Pier Side:** `:Gm#` (returns E#/W#/N# - primary method), fallback to `:GX4[n]#` for DestinationSideOfPier

**Data Structures:**
```python
class OnStepXDevice:
    def __init__(self, port: str, baud: int, timeout: float)
    def connect(self) -> bool
    def disconnect(self)
    def send_command(self, cmd: str) -> str
    def get_position(self) -> (float, float)  # RA, Dec in degrees
    def get_alt_az(self) -> (float, float)    # Alt, Az in degrees
    def goto_radec(self, ra: float, dec: float) -> int
    def is_slewing(self) -> bool
    def stop_slew(self)
    # ... etc
```

### 1.2 Telescope Device Layer (`telescopedevice.py`)

**Purpose:** Implement ASCOM telescope interface logic using OnStepX commands.

**Key Responsibilities:**
- Wrap `onstepx_device` with ASCOM semantics
- Convert between coordinate systems (degrees ↔ hours/HMS/DMS)
- Manage tracking state
- Handle slewing operations with proper state tracking
- Implement parking logic
- Rate limiting and command throttling
- Maintain device state cache to reduce OnStepX queries

**ASCOM Properties to Implement:**
- **Core:** `Connected`, `Name`, `Description`, `DriverInfo`, `DriverVersion`
- **Capabilities:** `CanFindHome`, `CanPark`, `CanPulseGuide`, `CanSetGuideRates`, `CanSetPark`, `CanSetPierSide`, `CanSetTracking`, `CanSlew`, `CanSlewAltAz`, `CanSlewAltAzAsync`, `CanSlewAsync`, `CanSync`, `CanSyncAltAz`, `CanUnpark`
- **Position:** `Altitude`, `Azimuth`, `Declination`, `RightAscension`
- **Target:** `TargetDeclination`, `TargetRightAscension`
- **State:** `AtHome`, `AtPark`, `Slewing`, `Tracking`, `IsPulseGuiding`
- **Site:** `SiteLatitude`, `SiteLongitude`, `SiteElevation`
- **Time:** `SiderealTime`, `UTCDate`
- **Mount:** `AlignmentMode` (GermanPolar/Polar/AltAz), `ApertureArea`, `ApertureDiameter`, `FocalLength`, `EquatorialSystem` (return equTopocentric), `DoesRefraction` (True - OnStepX does refraction internally)
- **Tracking:** `TrackingRate`, `TrackingRates` (return [0,1,2,3] for sidereal/lunar/solar/king), `DeclinationRate`, `RightAscensionRate`
- **Axis:** `AxisRates`, `CanMoveAxis`
- **Pier:** `DestinationSideOfPier`, `SideOfPier` (use `:Gm#` for E#/W#/N#)
- **Guide:** `GuideRateDeclination`, `GuideRateRightAscension`

**ASCOM Methods to Implement:**
- **Slewing:** `SlewToCoordinates`, `SlewToCoordinatesAsync`, `SlewToTarget`, `SlewToTargetAsync`, `SlewToAltAz`, `SlewToAltAzAsync`
- **Movement:** `MoveAxis`, `AbortSlew`
- **Park/Home:** `Park`, `SetPark`, `Unpark`, `FindHome`, `SetHome`
- **Sync:** `SyncToCoordinates`, `SyncToTarget`, `SyncToAltAz`
- **Guiding:** `PulseGuide`
- **Tracking:** Set via `Tracking` property

### 1.3 Alpaca API Responders (`telescope.py`)

**Purpose:** Map HTTP REST endpoints to telescope device methods.

**Based on:** `templates/telescope.py` with proper implementation.

**Pattern:**
```python
@before(PreProcessRequest(maxdev))
class rightascension:
    def on_get(self, req: Request, resp: Response, devnum: int):
        try:
            ra = device.right_ascension  # Get from telescopedevice
            resp.text = PropertyResponse(ra, req).json
        except Exception as ex:
            resp.text = PropertyResponse(None, req, 
                DriverException(0x500, 'RightAscension read failed', ex)).json
```

**Key Responders:**
- All ASCOM ITelescope properties (GET/PUT as appropriate)
- All ASCOM ITelescope methods (PUT)
- `connected`, `connecting`, `tracking`, `slewing`
- `rightascension`, `declination`, `altitude`, `azimuth`
- `slewtocoordinates`, `slewtocoordinatesasync`, `sideofpier`
- `park`, `unpark`, `findhome`, `abortslew`
- `pulseguide`, `movaxis`
- `synctocoordinates`

### 1.4 Configuration (`config.toml` and `config.py`)

**config.toml:**
```toml
title = "OnStepX Alpaca Driver (Telescope)"

[network]
ip_address = ''
port = 5555

[server]
location = 'Your Observatory'
verbose_driver_exceptions = true

[device]
type = 'telescope'
connection_type = 'serial'  # 'serial' or 'tcp' for WiFi OnStepX
serial_port = '/dev/ttyUSB0'  # or 'COM3' on Windows
tcp_host = '192.168.1.100'    # if connection_type = 'tcp'
tcp_port = 9999               # if connection_type = 'tcp'
baud_rate = 9600
timeout = 2.0
# OnStepX specific
aperture_diameter = 0.203  # meters (8 inch)
aperture_area = 0.032      # square meters
focal_length = 1.2         # meters
enable_focuser = false
enable_rotator = false
# Polling configuration
position_poll_interval = 0.25  # seconds (250ms)

[logging]
log_level = 'INFO'
log_to_stdout = true
max_size_mb = 5
num_keep_logs = 10
```

**config.py changes:**
Must be rewritten to load new telescope-specific fields instead of rotator fields (can_reverse, step_size, steps_per_sec). Add properties for serial_port, baud_rate, tcp_host, tcp_port, connection_type, aperture_diameter, aperture_area, focal_length, position_poll_interval.

### 1.5 Application Setup (`app.py` and `management.py`)

**Changes Required in `app.py`:**
1. Replace `import rotator` with `import telescope`
2. In `main()`, change routing:
   ```python
   # OLD: init_routes(app, 'rotator', rotator)
   # NEW:
   init_routes(app, 'telescope', telescope)
   ```
3. Initialize telescope device with config
4. Pass device instance to telescope module

**Changes Required in `management.py`:**
1. Replace `from rotator import RotatorMetadata` with `from telescope import TelescopeMetadata`
2. Update `configureddevices()` method to return telescope device info:
   ```python
   # OLD: 'DeviceType': RotatorMetadata.DeviceType,
   # NEW: 'DeviceType': TelescopeMetadata.DeviceType,
   ```
3. This is **CRITICAL** for Alpaca discovery to work correctly

**Metadata Update:**
```python
class TelescopeMetadata:
    Name = 'OnStepX Telescope'
    Version = '1.0.0'
    Description = 'ASCOM Alpaca Driver for OnStepX Controller'
    DeviceType = 'Telescope'
    DeviceID = '<GENERATE NEW GUID>'
    Info = 'OnStepX Alpaca Driver\nImplements ITelescopeV4\nASCOM Initiative'
    InterfaceVersion = 4
```

## Phase 2: Advanced Features (Optional)

### 2.1 Focuser Support
If `enable_focuser = true` in config:
- Implement `focuserdevice.py` using OnStepX focuser commands (`:F[n]#`, `:FG#`, `:FQ#`, etc.)
- Add focuser responders from `templates/focuser.py`
- Add second device routing in `app.py`

### 2.2 Rotator Support
If `enable_rotator = true` in config:
- Adapt existing `rotatordevice.py` to use OnStepX rotator commands (`:r[n]#`, `:rG#`, etc.)
- Modify `rotator.py` responders to use OnStepX backend
- Add rotator device routing in `app.py`

## Phase 3: Testing & Validation

### 3.1 Unit Testing
- Test OnStepX command parsing
- Test coordinate conversions
- Test state management

### 3.2 Integration Testing
- Connect to actual OnStepX hardware
- Verify all ASCOM properties return correct values
- Test goto/slewing operations
- Test parking/homing
- Test tracking modes

### 3.3 ASCOM Conformance
- Run ConformU Alpaca Protocol tests
- Run ConformU Telescope Device tests
- Address any conformance issues

## Implementation Details

### Coordinate Conversions

**OnStepX Format → ASCOM:**
- RA: `HH:MM:SS` → decimal hours (0-24)
- Dec: `sDD*MM:SS` → decimal degrees (-90 to +90)
- Alt: `sDD*MM'SS` → decimal degrees (-90 to +90)
- Az: `DDD*MM'SS` → decimal degrees (0-360)
- **Longitude: OnStepX east-negative → ASCOM east-positive (MUST NEGATE)**

**Helper Functions Needed:**
```python
def hms_to_hours(hms: str) -> float
def dms_to_degrees(dms: str) -> float
def hours_to_hms(hours: float) -> str
def degrees_to_dms(degrees: float, is_altitude: bool = False) -> str
```

**Critical Sign Convention:**
- When reading longitude from OnStepX (`:Gg#`): `ascom_lon = -onstepx_lon`
- When writing longitude to OnStepX (`:Sg#`): `onstepx_lon = -ascom_lon`

### Error Handling

**OnStepX Error Codes (`:MS#` returns):**
- 0: Success
- 1: Below horizon limit → `OperationFailedException`
- 2: Above overhead limit → `OperationFailedException`
- 3: Controller in standby → `NotConnectedException`
- 4: Mount is parked → `ParkedException`
- 5: Goto in progress → `InvalidOperationException`
- 6: Outside limits → `InvalidValueException`
- 7: Hardware fault → `DriverException`
- 8: Already in motion → `InvalidOperationException`
- 9: Unspecified error → `DriverException`

### Threading Considerations

- OnStepX communication must be thread-safe (use `threading.Lock`)
- Async slewing operations need background threads
- State polling for `Slewing` property (use `:D#` command)
- Careful with connection state during long operations

### Performance Optimization

1. **Caching:** Cache frequently read properties (position updates every 100-500ms)
2. **Batching:** Group related queries where possible
3. **Lazy Initialization:** Don't query capabilities until first access
4. **Rate Limiting:** Respect OnStepX command processing rate

## Dependencies

**Required Python Packages:**
- `falcon` (already in AlpycaDevice)
- `pyserial` (NEW - add to requirements)
- Standard library: `threading`, `time`, `logging`, `json`

## Success Criteria

1. ✅ Driver connects to OnStepX via serial
2. ✅ Responds to all Alpaca discovery requests
3. ✅ Exposes all required ASCOM telescope properties
4. ✅ Can slew to coordinates and track
5. ✅ Park/unpark operations work correctly
6. ✅ Passes ConformU protocol validation
7. ✅ Passes ConformU telescope validation (or documents known limitations)
8. ✅ Documentation complete with setup guide

## Known Limitations & Design Decisions

1. **Mount Type Detection:** Will need to query OnStepX capabilities or configure in config.toml
2. **Pier Side:** OnStepX doesn't have direct pier side query - must derive from axis positions
3. **Rate Support:** OnStepX has fixed rate sets, map to ASCOM DriveRates enum
4. **Sync Behavior:** OnStepX `:CS#` and `:CM#` have different semantics, choose appropriate
5. **Connection Timeout:** OnStepX has no explicit connect command, verify version query works

## Risk Mitigation

- **Serial Communication:** Implement robust error handling and reconnection logic
- **State Consistency:** Poll OnStepX state regularly, don't rely solely on cached values
- **Command Timing:** Some OnStepX commands take time (goto, park), implement proper async handling
- **Coordinate Systems:** Thoroughly test coordinate conversions with known good values

## Documentation Requirements

1. **README_ONSTEPX.md:** User-facing setup guide
2. **ONSTEPX_MAPPING.md:** OnStepX command → ASCOM property/method mapping
3. **Code Comments:** Docstrings for all public methods
4. **Configuration Guide:** Detailed config.toml explanation
