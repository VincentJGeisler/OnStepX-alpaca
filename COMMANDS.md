# OnStepX Command Reference

Complete command set for OnStepX telescope controller firmware (v10.27l).

## Table of Contents

1. [System Commands](#system-commands)
2. [Firmware Information](#firmware-information)
3. [Mount Position](#mount-position)
4. [Goto Commands](#goto-commands)
5. [Alignment](#alignment)
6. [Tracking](#tracking)
7. [Movement & Guiding](#movement--guiding)
8. [Park & Home](#park--home)
9. [Site & Time](#site--time)
10. [Limits](#limits)
11. [PEC (Periodic Error Correction)](#pec-periodic-error-correction)
12. [Library/Catalog](#librarycatalog)
13. [Rotator](#rotator)
14. [Focuser](#focuser)
15. [Auxiliary Features](#auxiliary-features)
16. [Status & Diagnostics](#status--diagnostics)

---

## System Commands

### :ERESET#
Reset the MCU
- **Returns:** Nothing
- **Note:** Reboots the controller

### :ENVRESET#
Wipe NV memory (EEPROM/Flash)
- **Returns:** "NV memory will be cleared on the next boot."
- **Note:** Clears all stored settings on next restart

### :ESPFLASH#
ESP8266 device flash mode
- **Returns:** 1 on completion (after up to one minute)
- **Note:** Puts ESP8266 WiFi module into firmware upload mode

### :EC[s]#
Echo string [s] as a debug message
- **Parameter:** String with spaces encoded as '_', newline as '&' at end
- **Returns:** Nothing
- **Example:** `:ECMSG:_Test_message&#`

### :B+#
Increase reticle brightness
- **Returns:** Nothing

### :B-#
Decrease reticle brightness
- **Returns:** Nothing

---

## Firmware Information

### :GVD#
Get firmware date
- **Returns:** MTH DD YYYY#
- **Example:** `FEB 06 2026#`

### :GVN#
Get firmware version number
- **Returns:** M.mp#
- **Example:** `10.27l#`

### :GVM#
Get firmware message
- **Returns:** s# (name and version)
- **Example:** `On-Step 10.27l#`

### :GVP#
Get product name
- **Returns:** s#
- **Example:** `On-Step#`

### :GVT#
Get firmware time
- **Returns:** HH:MM:SS#

### :GVC#
Get firmware config name
- **Returns:** s# (product description)

### :GVH#
Get firmware hardware
- **Returns:** s# (pinmap name)
- **Example:** `MaxPCB4#`

---

## Mount Position

### :GA#
Get mount altitude
- **Returns:** sDD\*MM# or sDD\*MM'SS# (based on precision)
- **Example:** `+45*30'15#`

### :GAH#
Get mount altitude (high precision)
- **Returns:** sDD\*MM'SS.SSS#

### :GD#
Get mount declination
- **Returns:** sDD\*MM# or sDD\*MM:SS#
- **Example:** `+12*34:56#`

### :GDH# / :GDe#
Get mount declination (high precision)
- **Returns:** sDD\*MM:SS.SSS#

### :GR#
Get mount right ascension
- **Returns:** HH:MM.T# or HH:MM:SS#
- **Example:** `14:30:00#`

### :GRH# / :GRa#
Get mount right ascension (high precision)
- **Returns:** HH:MM:SS.SSSS#

### :GZ#
Get mount azimuth
- **Returns:** DDD\*MM# or DDD\*MM:SS#

### :GZH#
Get mount azimuth (high precision)
- **Returns:** DDD\*MM'SS.SSS#

### :GX4[n]#
Get axis angles
- **Parameter n:**
  - 0: Axis1 in DDD:MM:SS
  - 1: Axis2 in DDD:MM:SS
  - 2: Axis1 in decimal degrees
  - 3: Axis2 in decimal degrees
  - 4: Axis1 encoder counts
  - 5: Axis2 encoder counts
- **Returns:** Angle or count as specified

---

## Goto Commands

### :Sr[HH:MM:SS]# or :Sr[HH:MM.T]#
Set target right ascension
- **Returns:** 1 on success, 0 on failure

### :Sd[sDD\*MM:SS]# or :Sd[sDD\*MM]#
Set target declination
- **Returns:** 1 on success, 0 on failure

### :Sa[sDD\*MM:SS]#
Set target altitude
- **Returns:** 1 on success

### :Sz[DDD\*MM:SS]#
Set target azimuth
- **Returns:** 1 on success

### :MS#
Goto target coordinates
- **Returns:** 0 on success, error code otherwise
  - 1: Below horizon limit
  - 2: Above overhead limit  
  - 3: Controller in standby
  - 4: Mount is parked
  - 5: Goto in progress
  - 6: Outside limits
  - 7: Hardware fault
  - 8: Already in motion
  - 9: Unspecified error

### :MA#
Goto target Alt/Az
- **Returns:** Error code as above

### :MP#
Goto current position for polar alignment
- **Returns:** Error code as above

### :MD#
Goto destination pier side for target
- **Returns:** Error code as above

### :Gr#
Get target right ascension
- **Returns:** HH:MM.T# or HH:MM:SS#

### :GrH#
Get target right ascension (high precision)
- **Returns:** HH:MM:SS.SSSS#

### :Gd#
Get target declination
- **Returns:** sDD\*MM# or sDD\*MM:SS#

### :GdH#
Get target declination (high precision)
- **Returns:** sDD\*MM:SS.SSS#

### :Gal#
Get target altitude
- **Returns:** sDD\*MM# or sDD\*MM:SS#

### :GaH#
Get target altitude (high precision)
- **Returns:** sDD\*MM'SS.SSS#

### :Gz#
Get target azimuth
- **Returns:** DDD\*MM# or DDD\*MM:SS#

### :GzH#
Get target azimuth (high precision)
- **Returns:** DDD\*MM'SS.SSS#

### :D#
Distance bars / movement check
- **Returns:** `\x7F#` if moving, `#` if stopped

---

## Alignment

### :A[n]#
Start manual alignment sequence
- **Parameter n:** Number of alignment stars (1-9)
- **Returns:** 1 on success, 0 on failure
- **Note:** Mount must be at home position first

### :A+#
Accept current position as alignment star
- **Returns:** 1 on success, 0 on failure

### :A?#
Get alignment status
- **Returns:** mno#
  - m: Maximum number of stars
  - n: Current star (0 if not aligning)
  - o: Last star required (0 if not aligning)

### :AW#
Write alignment model to EEPROM
- **Returns:** 1 on success

### :CS#
Sync telescope to current RA/Dec coordinates
- **Returns:** Nothing (fails silently)

### :CM#
Sync telescope to current target
- **Returns:** `N/A#` on success, `En#` on error (n = error code 1-9)

---

## Tracking

### :GT#
Get tracking rate
- **Returns:** n.nnnnn# (rate in Hz, 0 if not tracking)

### :T+#
Enable tracking
- **Returns:** 1 on success

### :T-#
Disable tracking
- **Returns:** 1 on success

### :TS#
Set tracking rate: Solar (60 Hz)
- **Returns:** 1 on success

### :TL#
Set tracking rate: Lunar
- **Returns:** 1 on success

### :TQ#
Set tracking rate: Sidereal
- **Returns:** 1 on success

### :TK#
Set tracking rate: King (sidereal + 0.014 arcsec/sec)
- **Returns:** 1 on success

### :GXTR#
Get tracking rate offset RA
- **Returns:** n.nn# (arcseconds per sidereal second)

### :GXTD#
Get tracking rate offset Dec
- **Returns:** n.nn# (arcseconds per sidereal second)

### :SXTR,n.n#
Set tracking rate offset RA
- **Parameter:** Arcseconds per sidereal second
- **Returns:** 1 on success

### :SXTD,n.n#
Set tracking rate offset Dec
- **Parameter:** Arcseconds per sidereal second
- **Returns:** 1 on success

---

## Movement & Guiding

### :Mw#
Move west at guide rate
- **Returns:** Nothing

### :Me#
Move east at guide rate
- **Returns:** Nothing

### :Mn#
Move north at guide rate
- **Returns:** Nothing

### :Ms#
Move south at guide rate
- **Returns:** Nothing

### :Mp#
Move in spiral search pattern
- **Returns:** Nothing

### :Q#
Halt all movement/goto
- **Returns:** Nothing

### :Qe# / :Qw#
Halt east/west movement
- **Returns:** Nothing

### :Qn# / :Qs#
Halt north/south movement
- **Returns:** Nothing

### :Mgd[n]# / :MGd[n]#
Pulse guide (Dec axis)
- **Parameter n:** Guide time in milliseconds
- **Returns:** Nothing

### :Mgr[n]# / :MGr[n]#
Pulse guide (RA axis)
- **Parameter n:** Guide time in milliseconds
- **Returns:** Nothing

### :RG#
Set guide rate: Guiding (1x sidereal)
- **Returns:** Nothing

### :RC#
Set guide rate: Centering (8x)
- **Returns:** Nothing

### :RM#
Set guide rate: Find (20x)
- **Returns:** Nothing

### :RF#
Set guide rate: Fast (48x)
- **Returns:** Nothing

### :RS#
Set guide rate: Slew (1/2 of goto rate)
- **Returns:** Nothing

### :Rn#
Set guide rate by number
- **Parameter n:** Rate 0-9
- **Returns:** Nothing

### :RA[n.n]#
Set Axis1 guide rate
- **Parameter:** Degrees per second
- **Returns:** 1 on success

### :RE[n.n]#
Set Axis2 guide rate
- **Parameter:** Degrees per second
- **Returns:** 1 on success

### :GX90#
Get pulse guide rate setting
- **Returns:** n# (guide rate multiplier)

---

## Park & Home

### :hP#
Move to park position
- **Returns:** 1 on success, 0 if already parked or in motion

### :hQ#
Set current position as park position
- **Returns:** 1 on success

### :hR#
Restore parked mount to operation (unpark)
- **Returns:** 1 on success

### :hC#
Move to home position
- **Returns:** 1 on success

### :hF#
Reset at home position (set home)
- **Returns:** 1 on success
- **Note:** Required after cold start

### :h?#
Get home status
- **Returns:** n,n,snnnnn,snnnnn#
  - Has sense (0/1)
  - Auto home enabled (0/1)
  - Axis1 offset (arcseconds)
  - Axis2 offset (arcseconds)

### :hAn#
Set auto-home state
- **Parameter n:** 0=disabled, 1=enabled
- **Returns:** 1 on success

### :hC1,n#
Set Axis1 home sense direction and offset
- **Parameter n:** Offset in arcseconds
- **Returns:** 1 on success

### :hC2,n#
Set Axis2 home sense direction and offset
- **Parameter n:** Offset in arcseconds
- **Returns:** 1 on success

---

## Site & Time

### :Gg#
Get site longitude
- **Returns:** sDDD\*MM# (east is negative)

### :GgH#
Get site longitude (high precision)
- **Returns:** sDDD\*MM:SS#

### :Sg[sDDD\*MM]# or :Sg[sDDD\*MM:SS]#
Set site longitude
- **Returns:** 1 on success

### :Gt#
Get site latitude
- **Returns:** sDD\*MM#

### :GtH#
Get site latitude (high precision)
- **Returns:** sDD\*MM:SS#

### :St[sDD\*MM]# or :St[sDD\*MM:SS]#
Set site latitude
- **Returns:** 1 on success

### :Gv#
Get site elevation
- **Returns:** snnnnn# (meters)

### :Sv[n]#
Set site elevation
- **Parameter n:** Elevation in meters
- **Returns:** 1 on success

### :GS#
Get sidereal time
- **Returns:** HH:MM:SS# (24-hour format)

### :GSH#
Get sidereal time (high precision)
- **Returns:** HH:MM:SS.ss#

### :GL#
Get local time
- **Returns:** HH:MM:SS# (24-hour format)

### :GLH#
Get local time (high precision)
- **Returns:** HH:MM:SS.SSSS#

### :Ga#
Get local time (12-hour format)
- **Returns:** HH:MM:SS#

### :GC#
Get calendar date
- **Returns:** MM/DD/YY#

### :SC[MM/DD/YY]#
Set calendar date
- **Returns:** 1 on success, 0 on error

### :SL[HH:MM:SS]#
Set local time
- **Returns:** 1 on success

### :GG#
Get UTC offset
- **Returns:** sHH# or sHH:MM#

### :SG[sHH]# or :SG[sHH:MM]#
Set UTC offset
- **Returns:** 1 on success

### :Gc#
Get time format
- **Returns:** 12# or 24#

### :Sc[n]#
Set time format
- **Parameter n:** 12 or 24
- **Returns:** 1 on success

### :GM# / :GN# / :GO# / :GP#
Get site name (sites 1-4)
- **Returns:** Site name (up to 16 chars)

### :SM[name]# / :SN[name]# / :SO[name]# / :SP[name]#
Set site name
- **Returns:** 1 on success

### :GX80#
Get UT1 time
- **Returns:** HH:MM:SS#

### :GX81#
Get UT1 date
- **Returns:** MM/DD/YY#

### :GX89#
Get date/time ready status
- **Returns:** 1 if ready, 0 if not

---

## Limits

### :Gh#
Get horizon limit
- **Returns:** sDD\*# (minimum elevation)
- **Note:** For FORK mounts, this is DEC-based, not altitude-based

### :Sh[sDD]#
Set horizon limit
- **Returns:** 1 on success

### :Go#
Get overhead limit
- **Returns:** DD\*#
- **Note:** For FORK mounts, this is DEC-based (0-90°), for others altitude (60-90°)

### :So[DD]#
Set overhead limit
- **Returns:** 1 on success

### :GXE[m]#
Get other limit settings
- **Parameter m:** Limit type
- **Returns:** Varies by parameter

---

## PEC (Periodic Error Correction)

### :$QZ+#
Enable PEC
- **Returns:** Nothing

### :$QZ-#
Disable PEC
- **Returns:** Nothing

### :$QZ/#
Ready PEC recording
- **Returns:** Nothing

### :$QZ!#
Write PEC data to non-volatile memory
- **Returns:** Nothing

### :$QZZ#
Clear PEC buffer
- **Returns:** Nothing

### :$QZ?#
Get PEC status
- **Returns:** Status code

### :GX91#
Get PEC analog value
- **Returns:** n#

### :GXE6#
Get steps per sidereal second
- **Returns:** n#

### :GXE7#
Get PEC worm rotation steps (from NV)
- **Returns:** n#

### :GXE8#
Get PEC buffer size
- **Returns:** n# (seconds)

### :SXE7,[n]#
Set PEC worm rotation steps
- **Returns:** 1 on success

### :VR[n]#
Read PEC table entry
- **Parameter n:** Worm segment (seconds)
- **Returns:** Rate adjustment in steps

### :VR#
Read currently playing PEC entry
- **Returns:** Segment and rate adjustment

### :Vr[n]#
Read PEC ten-byte frame (hex)
- **Parameter n:** Starting segment
- **Returns:** Hex data

### :VS#
Get PEC steps per sidereal second
- **Returns:** n#

### :VW#
Get PEC worm rotation steps
- **Returns:** n#

### :WR+#
Move PEC table ahead one second
- **Returns:** Nothing

### :WR-#
Move PEC table back one second
- **Returns:** Nothing

### :WR[n,sn]#
Write PEC table entry
- **Parameters:** Segment n, signed adjustment sn
- **Returns:** 1 on success

---

## Library/Catalog

### :LB#
Find previous catalog object
- **Returns:** Nothing

### :LN#
Find next catalog object
- **Returns:** Nothing

### :LC[n]#
Select catalog object by number
- **Parameter n:** Object number
- **Returns:** 1 on success

### :LI#
Get object information
- **Returns:** Object data string

### :LIG#
Get object info and goto
- **Returns:** Object data, then initiates goto

### :LR#
Get catalog object and advance
- **Returns:** Object data including RA/Dec

### :LW[s]#
Write catalog entry
- **Parameter s:** Object data
- **Returns:** 1 on success

### :L$#
Move to catalog name record
- **Returns:** Nothing

### :LD#
Clear current record
- **Returns:** 1 on success

### :LL#
Clear current catalog
- **Returns:** 1 on success

### :L!#
Clear entire library
- **Returns:** 1 on success

### :L?#
Get free records count
- **Returns:** n#

### :Lo[n]#
Select catalog by number
- **Parameter n:** Catalog number
- **Returns:** 1 on success

---

## Rotator

### :rA#
Check if rotator active
- **Returns:** 1 if active, 0 if not

### :rT#
Get rotator status
- **Returns:** Status string

### :rI#
Get minimum position
- **Returns:** n# (degrees)

### :rM#
Get maximum position
- **Returns:** n# (degrees)

### :rD#
Get degrees per step
- **Returns:** n.nnn#

### :rb#
Get backlash
- **Returns:** n# (steps)

### :rb[n]#
Set backlash
- **Parameter n:** Steps
- **Returns:** 1 on success

### :rQ#
Stop rotator movement
- **Returns:** Nothing

### :r[n]#
Set move/goto rate
- **Parameter n:** Rate setting
- **Returns:** 1 on success

### :rW#
Get working slew rate
- **Returns:** n.n# (deg/s)

### :rc#
Set continuous move mode
- **Returns:** 1 on success

### :r>#
Move clockwise
- **Returns:** Nothing

### :r<#
Move counter-clockwise
- **Returns:** Nothing

### :rG#
Get current angle
- **Returns:** sDDD\*MM# or sDDD\*MM:SS#

### :rr[sDDD\*MM]#
Set target angle (relative move)
- **Returns:** 1 on success

### :rS[sDDD\*MM]#
Set target angle (absolute position)
- **Returns:** 1 on success

### :rZ#
Set position to zero
- **Returns:** 1 on success

### :rF#
Set position to half-travel
- **Returns:** 1 on success

### :rC#
Move to half-travel position
- **Returns:** Nothing

### :r+#
Enable derotator
- **Returns:** 1 on success

### :r-#
Disable derotator
- **Returns:** 1 on success

### :rR#
Reverse derotator direction
- **Returns:** 1 on success

### :rP#
Move to parallactic angle
- **Returns:** Nothing

### :hP#
Park rotator
- **Returns:** 1 on success

### :hR#
Unpark rotator
- **Returns:** 1 on success

### :GX98#
Get rotator availability
- **Returns:** 1 if available, 0 if not

---

## Focuser

Focuser commands use F for first/default focuser, F1-F6 for specific focusers.

### :FA#
Check if focuser active
- **Returns:** 1 if active, 0 if not

### :FA[n]#
Select focuser
- **Parameter n:** Focuser number (1-6)
- **Returns:** 1 on success

### :Fa#
Get primary focuser number
- **Returns:** n#

### :FT#
Get focuser status
- **Returns:** Status code

### :Fp#
Get focuser mode
- **Returns:** Mode code

### :FI#
Get full-in position
- **Returns:** n# (microns or steps)

### :FM#
Get maximum position
- **Returns:** n# (microns or steps)

### :FG#
Get current position
- **Returns:** n# (microns or steps)

### :Fe#
Get temperature differential
- **Returns:** n.n# (°C)

### :Ft#
Get focuser temperature
- **Returns:** n.n# (°C)

### :Fu#
Get microns per step
- **Returns:** n.n#

### :FB#
Get backlash
- **Returns:** n# (steps or microns)

### :FB[n]#
Set backlash
- **Parameter n:** Steps or microns
- **Returns:** 1 on success

### :FC#
Get temperature compensation coefficient
- **Returns:** sn.n# (microns per °C)

### :FC[sn.n]#
Set temperature compensation coefficient
- **Parameter:** Microns per °C (+ moves out as temp falls)
- **Returns:** 1 on success

### :Fc#
Get temperature compensation enable status
- **Returns:** 1 if enabled, 0 if disabled

### :Fc[n]#
Enable/disable temperature compensation
- **Parameter n:** 0=disabled, 1=enabled
- **Returns:** 1 on success

### :FD#
Get temperature compensation deadband
- **Returns:** n# (steps or microns)

### :FD[n]#
Set temperature compensation deadband
- **Parameter n:** Steps or microns
- **Returns:** 1 on success

### :FP#
Get DC motor power level
- **Returns:** n# (percent)

### :FP[n]#
Set DC motor power level
- **Parameter n:** Percent (0-100)
- **Returns:** 1 on success

### :FQ#
Stop focuser
- **Returns:** Nothing

### :F+#
Move focuser in (toward telescope)
- **Returns:** Nothing

### :F-#
Move focuser out (away from telescope)
- **Returns:** Nothing

### :FF#
Move to full-in position
- **Returns:** Nothing

### :FS[n]#
Set target position
- **Parameter n:** Position in microns or steps
- **Returns:** 1 on success

### :FG#
Goto target position
- **Returns:** Nothing

### :FZ#
Set current position as zero
- **Returns:** 1 on success

### :FH#
Set current position as half-travel
- **Returns:** 1 on success

### :hP#
Park all focusers
- **Returns:** 1 on success

### :hR#
Unpark all focusers
- **Returns:** 1 on success

---

## Auxiliary Features

### :GXX[n]#
Get auxiliary feature status
- **Parameter n:** Feature number
- **Returns:** Status value

### :GXY[n]#
Get auxiliary feature value
- **Parameter n:** Feature number
- **Returns:** Value

### :GXY0#
Get auxiliary feature count
- **Returns:** n# (number of features)

### :SXX[n],V[Z][S][v]#
Set auxiliary feature
- **Parameters:** Feature n, value V, optional zone Z, switch S, variable v
- **Returns:** 1 on success

---

## Status & Diagnostics

### :GU#
Get telescope status (long form)
- **Returns:** Multi-character status string

### :Gu#
Get telescope status (bit-packed)
- **Returns:** Hex status value

### :GW#
Get tracking and basic mount state
- **Returns:** Status string

### :Gm#
Get meridian pier side
- **Returns:** E# (East) or W# (West) or N# (None)

### :SX97,[n]#
Set buzzer state/duration
- **Parameter n:** Beep duration in milliseconds
- **Returns:** 1 on success

### :GX9A#
Get temperature
- **Returns:** sn.n# (°C)

### :GX9B#
Get pressure
- **Returns:** n.n# (mb)

### :GX9C#
Get relative humidity
- **Returns:** n.n# (percent)

### :GX9E#
Get dew point
- **Returns:** sn.n# (°C)

### :GX9F#
Get MCU temperature
- **Returns:** n# (°C)

### :SX9A,[sn.n]#
Set temperature override
- **Returns:** 1 on success

### :SX9B,[n.n]#
Set pressure override
- **Returns:** 1 on success

### :SX9C,[n.n]#
Set humidity override
- **Returns:** 1 on success

### :GXA0#
Get axis/driver revert state
- **Returns:** n# (0=NV settings, 1=Config.h settings)

### :SXAC,0# / :SXAC,1#
Set axis settings source
- **Parameter:** 0=runtime NV, 1=compile-time Config.h
- **Returns:** 1 on success

### :GXFn#
Get frequency and workload
- **Returns:** Frequency and CPU usage data

---

## Notes

### Command Format
- Commands are case-sensitive
- Commands terminate with `#`
- Responses terminate with `#`
- Numeric parameters: n = integer, n.n = float
- Angle parameters: s = sign (+/-), DD = degrees, MM = arcminutes, SS = arcseconds
- Time parameters: HH = hours, MM = minutes, SS = seconds

### Return Values
- `1` = Success (for most set commands)
- `0` = Failure
- Numeric reply flag controls whether response is followed by additional `#`

### Coordinate Formats
- **DMS:** `sDD*MM:SS` (e.g., `+45*30:15`)
- **HMS:** `HH:MM:SS` (e.g., `14:30:00`)
- **Decimal:** `n.nnnnnn` (degrees or hours)

### FORK Mount Special Behavior
This fork implements FORK mount limit handling differently from upstream:
- Horizon/overhead limits check **declination** (mechanical) instead of altitude (sky coordinates)
- Directional limit enforcement allows movement away from limits
- Goto recovery enabled when parked outside limits

See README.md "Fork Differences" section for details.

---

**Document Version:** 1.0  
**Firmware Version:** OnStepX 10.27l  
**Last Updated:** 2026-05-06
