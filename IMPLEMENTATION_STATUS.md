# OnStepX Alpaca Driver - Implementation Status

## Summary
Core implementation complete with 4 out of 5 major files finished. telescope.py needs completion of operational responders.

## Completed Components ✅

### 1. onstepx_device.py (COMPLETE)
Low-level OnStepX serial/TCP communication module
- Serial and TCP connection support
- All critical OnStepX commands implemented
- Thread-safe operations with locking
- Coordinate conversion helpers (HMS/DMS ↔ decimal)
- **Critical features:**
  - Connection validation via `:GVP#`
  - Longitude sign inversion (OnStepX east-negative ↔ ASCOM east-positive)
  - High-precision position reading (`:GRH#`, `:GDH#`, `:GAH#`, `:GZH#`)
  - Pier side via `:Gm#` (E#/W#/N#)
  - Status via `:GU#`
  - Goto with error code handling (`:MS#`)
  - Pulse guiding (`:Mgd#`, `:Mgr#`)
  - Tracking modes (`:TQ#`/`:TL#`/`:TS#`/`:TK#`)
  - Park/home operations

### 2. telescopedevice.py (COMPLETE)
ASCOM telescope device logic layer
- Wraps OnStepXDevice with ASCOM semantics
- **Background polling thread** - updates cached position/status every 250ms
- All ASCOM ITelescope properties implemented
- All ASCOM ITelescope methods implemented
- **Key features:**
  - Thread-safe state management
  - IsPulseGuiding tracking (timer-based)
  - Pier side mapping (E→0, W→1, N→-1)
  - Async and sync slewing operations
  - Goto error code to ASCOM exception mapping
  - Site location properties with coordinate conversions
  - Capability properties (Can*)
  - Tracking rate management

### 3. config.toml (COMPLETE)
Configuration file with OnStepX-specific settings
- Connection: serial_port, tcp_host, tcp_port, baud_rate, timeout
- Device type: telescope
- Connection type: serial or tcp
- Optics: aperture_diameter, aperture_area, focal_length
- Polling: position_poll_interval (250ms default)
- Optional features: enable_focuser, enable_rotator

### 4. config.py (COMPLETE)
Configuration loader
- Removed rotator-specific fields
- Added 10+ telescope-specific properties
- Loads from config.toml using existing pattern

### 5. management.py (COMPLETE)
Device management and discovery
- Updated to import TelescopeMetadata instead of RotatorMetadata
- configureddevices() returns telescope device info
- **Critical for Alpaca discovery**

### 6. app.py (COMPLETE)
Application initialization and routing
- Import changed from rotator to telescope
- Routing changed to telescope endpoints
- Device initialization updated to telescope

## Partially Complete ⚠️

### telescope.py (230 lines / ~1000 lines needed)
Alpaca API HTTP responders

**What's Complete:**
- Header section with imports
- TelescopeMetadata with OnStepX info
- Symbolic enums (AlignmentModes, DriveRates, etc.)
- Global device instance declaration
- Core responders (13 implemented):
  - action, commandblind, commandbool, commandstring (NotImplemented)
  - connected (GET/PUT) ✅
  - connecting (GET) ✅
  - description, driverinfo, driverversion, interfaceversion, name ✅
  - supportedactions ✅

**What's Missing:**
All operational telescope responders (~70 more classes needed):

**Position Properties:**
- rightascension (GET)
- declination (GET)
- altitude (GET)
- azimuth (GET)
- sideofpier (GET/PUT)
- destinationsideofpier (GET)

**Target Properties:**
- targetrightascension (GET/PUT)
- targetdeclination (GET/PUT)

**State Properties:**
- slewing (GET)
- tracking (GET/PUT)
- atpark (GET)
- athome (GET)
- ispulseguiding (GET)

**Site Properties:**
- sitelatitude (GET/PUT)
- sitelongitude (GET/PUT)
- siteelevation (GET/PUT)

**Time Properties:**
- siderealtime (GET)
- utcdate (GET/PUT)

**Mount Properties:**
- alignmentmode (GET)
- aperturearea (GET)
- aperturediameter (GET)
- focallength (GET)
- doesrefraction (GET)
- equatorialsystem (GET)

**Tracking Properties:**
- trackingrate (GET/PUT)
- trackingrates (GET)
- declinationrate (GET/PUT)
- rightascensionrate (GET/PUT)

**Guide Properties:**
- guideratedeclination (GET/PUT)
- guideraterightascension (GET/PUT)

**Capability Properties (all GET only):**
- canfindhome, canpark, canpulseguide, cansetguiderates, cansetpark, cansetpierside, cansettracking, canslew, canslewasync, canslewaltaz, canslewaltazasync, cansync, cansyncaltaz, canunpark, canmoveaxis

**Slewing Methods (all PUT):**
- slewtocoordinates
- slewtocoordinatesasync
- slewtotarget
- slewtotargetasync
- slewtoaltaz
- slewtoaltazasync
- abortslew

**Park/Home Methods (all PUT):**
- park
- setpark
- unpark
- findhome

**Sync Methods (all PUT):**
- synctocoordinates
- synctotarget
- synctoaltaz

**Guiding Methods:**
- pulseguide (PUT)

**Axis Methods:**
- moveaxis (PUT)
- axisrates (GET)

## Implementation Pattern for Missing Responders

Each responder follows this pattern (from rotator.py):

```python
@before(PreProcessRequest(maxdev))
class rightascension:
    def on_get(self, req: Request, resp: Response, devnum: int):
        if not device.connected:
            resp.text = PropertyResponse(None, req, NotConnectedException()).json
            return
        try:
            val = device.right_ascension
            resp.text = PropertyResponse(val, req).json
        except Exception as ex:
            resp.text = PropertyResponse(None, req,
                DriverException(0x500, 'Telescope.RightAscension failed', ex)).json
```

For PUT methods with parameters:
```python
@before(PreProcessRequest(maxdev))
class slewtocoordinates:
    def on_put(self, req: Request, resp: Response, devnum: int):
        if not device.connected:
            resp.text = MethodResponse(req, NotConnectedException()).json
            return
        try:
            ra = float(get_request_field('RightAscension', req))
            dec = float(get_request_field('Declination', req))
            device.slew_to_coordinates(ra, dec)
            resp.text = MethodResponse(req).json
        except Exception as ex:
            resp.text = MethodResponse(req,
                DriverException(0x500, 'Telescope.SlewToCoordinates failed', ex)).json
```

## Completion Steps

1. **Add device import** to telescope.py:
   ```python
   from telescopedevice import TelescopeDevice
   device: TelescopeDevice = None
   ```

2. **Add initialization function** at end of telescope.py:
   ```python
   def start_tel_device(config, _logger):
       global logger, device
       logger = _logger
       device = TelescopeDevice(logger, config)
       logger.info('Telescope device initialized')
   ```

3. **Append ~70 responder classes** following the pattern above
   - Use `device.property_name` for GET
   - Use `device.property_name = value` for PUT (writable properties)
   - Use `device.method_name(args)` for methods
   - Always check `device.connected` first (except for connected/connecting/name/description/etc)
   - Wrap in try/except with appropriate ASCOM exceptions

4. **Reference files:**
   - `device/rotator.py` lines 100-700 - complete working examples
   - `templates/telescope.py` - skeleton with all endpoint names
   - IMPLEMENTATION_PLAN.md - property/method mapping

## Testing Plan

Once telescope.py is complete:

1. **Syntax check:** `python -m py_compile device/telescope.py`
2. **Import test:** `python -c "import sys; sys.path.insert(0, 'device'); import telescope"`
3. **Start server:** `python device/app.py`
4. **Test discovery:** `curl http://localhost:5555/management/v1/description`
5. **Test connection:** `curl -X PUT http://localhost:5555/api/v1/telescope/0/connected -d "Connected=true"`
6. **Test properties:** `curl http://localhost:5555/api/v1/telescope/0/rightascension`

## Final Design Compliance Check

After telescope.py completion, run Opus review agent to verify:
- All ASCOM ITelescope properties/methods implemented
- Correct use of OnStepX commands
- Proper error handling and ASCOM exceptions
- Thread safety
- Longitude sign inversion correctly applied
- Pier side mapping correct (E→0, W→1, N→-1)
- All Opus review required changes incorporated

## Dependencies

Python packages needed (add to requirements.txt):
- falcon (already present)
- pyserial (NEW - for serial communication)
- Standard library: threading, time, logging, datetime, json, re

## Documentation TODO

After implementation complete:
- README_ONSTEPX.md - User setup guide
- ONSTEPX_MAPPING.md - Command to ASCOM property mapping
- Update main README.md - OnStepX driver section
