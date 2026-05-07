# -*- coding: utf-8 -*-
# =================================================================
# telescopedevice.py - OnStepX Telescope Device Logic Layer
# =================================================================
#
# ASCOM Alpaca telescope device implementation for OnStepX controller
# Wraps OnStepXDevice with ASCOM ITelescope semantics
#
# Author: Generated for OnStepX
# Python Compatibility: Requires Python 3.7 or later
#
# =================================================================

import threading
import time
from datetime import datetime, timezone
from threading import Timer, Lock
from logging import Logger
from typing import List, Tuple
from onstepx_device import OnStepXDevice
from exceptions import *

class TelescopeDevice:
    """OnStepX telescope device with ASCOM ITelescope interface.

    Wraps OnStepXDevice communication layer with ASCOM semantics,
    background polling, state caching, and thread-safe operations.
    """

    def __init__(self, logger: Logger, config, onstepx=None):
        """Initialize telescope device.

        Args:
            logger: Python logger instance
            config: Configuration object with device settings
            onstepx: Optional shared OnStepXDevice instance (created by app.py)
                    If None, creates a new instance (backward compatible)
        """
        self.logger = logger
        self.config = config
        self._lock = Lock()

        # Initialize OnStepX hardware interface
        if onstepx is not None:
            # Use shared connection instance
            self._onstepx = onstepx
        else:
            # Create new instance (backward compatibility)
            self._onstepx = OnStepXDevice(
                logger=logger,
                port=config.serial_port,
                baud=config.baud_rate,
                timeout=config.timeout,
                connection_type=config.connection_type,
                tcp_host=getattr(config, 'tcp_host', None),
                tcp_port=getattr(config, 'tcp_port', None)
            )

        # Connection state
        self._connected = False
        self._connecting = False

        # Cached position/status (updated by polling thread)
        self._cached_ra = 0.0  # hours
        self._cached_dec = 0.0  # degrees
        self._cached_alt = 0.0  # degrees
        self._cached_az = 0.0  # degrees
        self._cached_slewing = False
        self._cached_tracking = False
        self._cached_at_park = False
        self._cached_at_home = False
        self._cached_pier_side = -1  # pierUnknown

        # Target coordinates
        self._target_ra = 0.0  # hours
        self._target_dec = 0.0  # degrees

        # Pulse guiding state
        self._pulse_guide_start = 0.0
        self._pulse_guide_duration = 0.0

        # Configuration from config
        self._aperture_diameter = config.aperture_diameter
        self._aperture_area = config.aperture_area
        self._focal_length = config.focal_length
        self._poll_interval = config.position_poll_interval

        # Background polling thread
        self._poll_thread = None
        self._poll_running = False

    def connect(self) -> bool:
        """Connect to OnStepX hardware and auto-sync time if needed."""
        with self._lock:
            if self._connected:
                return True
            self._connecting = True

        try:
            success = self._onstepx.connect()
            if success:
                # Auto-sync time if OnStepX time differs from system time
                # (OnStepX loses time on power down, this is critical for safety)
                try:
                    import datetime
                    onstep_time = self._onstepx.get_utc_date()
                    system_time = datetime.datetime.now(datetime.timezone.utc)

                    # If times differ by more than 10 seconds, sync
                    time_diff = abs((system_time - onstep_time).total_seconds())
                    if time_diff > 10:
                        self.logger.warning(f'OnStepX time off by {time_diff:.0f}s, syncing to system time')
                        self._onstepx.set_utc_date(system_time)
                        self.logger.info(f'OnStepX time synchronized to {system_time.isoformat()}')
                    else:
                        self.logger.info(f'OnStepX time OK (diff {time_diff:.1f}s)')
                except Exception as ex:
                    self.logger.error(f'Failed to sync OnStepX time: {ex}')
                    self.logger.warning('OnStepX may refuse movement commands without correct time set')

                # Check if location is unset (0,0 - unless you're on a boat at the equator)
                try:
                    lat = self._onstepx.get_site_latitude()
                    lon = self._onstepx.get_site_longitude()
                    if lat == 0.0 and lon == 0.0:
                        self.logger.warning('OnStepX location is (0,0). Set via sitelatitude/sitelongitude unless you are on a boat at the equator.')
                except Exception as ex:
                    self.logger.debug(f'Could not check location: {ex}')

                with self._lock:
                    self._connected = True
                    self._connecting = False
                # Start background polling
                self._start_polling()
                self.logger.info('OnStepX telescope connected')
                return True
            else:
                with self._lock:
                    self._connecting = False
                return False
        except Exception as ex:
            with self._lock:
                self._connecting = False
            self.logger.error(f'Connect failed: {ex}')
            raise DriverException(0x500, f'Connection failed: {ex}')

    def disconnect(self):
        """Disconnect from OnStepX hardware."""
        self._stop_polling()
        with self._lock:
            if self._connected:
                self._onstepx.disconnect()
                self._connected = False
                self.logger.info('OnStepX telescope disconnected')

    def _start_polling(self):
        """Start background polling thread."""
        if not self._poll_running:
            self._poll_running = True
            self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._poll_thread.start()

    def _stop_polling(self):
        """Stop background polling thread."""
        self._poll_running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=2.0)

    def _poll_loop(self):
        """Background thread that polls OnStepX for position/status."""
        while self._poll_running:
            try:
                # Get position
                ra, dec = self._onstepx.get_position()
                alt, az = self._onstepx.get_alt_az()

                # Get status
                is_slewing = self._onstepx.is_slewing()
                tracking_rate = self._onstepx.get_tracking_rate()
                is_tracking = tracking_rate > 0

                # Get pier side
                pier_str = self._onstepx.get_pier_side()
                if pier_str == 'E':
                    pier_side = 0  # pierEast
                elif pier_str == 'W':
                    pier_side = 1  # pierWest
                else:
                    pier_side = -1  # pierUnknown

                # Update cached values
                with self._lock:
                    self._cached_ra = ra
                    self._cached_dec = dec
                    self._cached_alt = alt
                    self._cached_az = az
                    self._cached_slewing = is_slewing
                    self._cached_tracking = is_tracking
                    self._cached_pier_side = pier_side

            except Exception as ex:
                self.logger.error(f'Poll error: {ex}')

            time.sleep(self._poll_interval)

    # ==================== ASCOM Properties ====================

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._connected

    @property
    def connecting(self) -> bool:
        with self._lock:
            return self._connecting

    # Position properties
    @property
    def right_ascension(self) -> float:
        """Current RA in hours (0-24)."""
        with self._lock:
            return self._cached_ra

    @property
    def declination(self) -> float:
        """Current Dec in degrees (-90 to +90)."""
        with self._lock:
            return self._cached_dec

    @property
    def altitude(self) -> float:
        """Current altitude in degrees."""
        with self._lock:
            return self._cached_alt

    @property
    def azimuth(self) -> float:
        """Current azimuth in degrees (0-360)."""
        with self._lock:
            return self._cached_az

    # Target properties
    @property
    def target_right_ascension(self) -> float:
        with self._lock:
            return self._target_ra

    @target_right_ascension.setter
    def target_right_ascension(self, value: float):
        with self._lock:
            self._target_ra = value

    @property
    def target_declination(self) -> float:
        with self._lock:
            return self._target_dec

    @target_declination.setter
    def target_declination(self, value: float):
        with self._lock:
            self._target_dec = value

    # State properties
    @property
    def slewing(self) -> bool:
        with self._lock:
            return self._cached_slewing

    @property
    def tracking(self) -> bool:
        with self._lock:
            return self._cached_tracking

    @tracking.setter
    def tracking(self, value: bool):
        self._onstepx.set_tracking(value)
        with self._lock:
            self._cached_tracking = value

    @property
    def at_park(self) -> bool:
        with self._lock:
            return self._cached_at_park

    @property
    def at_home(self) -> bool:
        with self._lock:
            return self._cached_at_home

    @property
    def is_pulse_guiding(self) -> bool:
        """True if pulse guide is in progress."""
        now = time.time()
        with self._lock:
            if self._pulse_guide_start > 0:
                elapsed = (now - self._pulse_guide_start) * 1000  # ms
                return elapsed < self._pulse_guide_duration
        return False

    # Site properties
    @property
    def site_latitude(self) -> float:
        lat, lon, elev = self._onstepx.get_site_location()
        return lat

    @site_latitude.setter
    def site_latitude(self, value: float):
        lat, lon, elev = self._onstepx.get_site_location()
        self._onstepx.set_site_location(value, lon, elev)

    @property
    def site_longitude(self) -> float:
        lat, lon, elev = self._onstepx.get_site_location()
        return lon

    @site_longitude.setter
    def site_longitude(self, value: float):
        lat, lon, elev = self._onstepx.get_site_location()
        self._onstepx.set_site_location(lat, value, elev)

    @property
    def site_elevation(self) -> float:
        lat, lon, elev = self._onstepx.get_site_location()
        return elev

    @site_elevation.setter
    def site_elevation(self, value: float):
        lat, lon, elev = self._onstepx.get_site_location()
        self._onstepx.set_site_location(lat, lon, value)

    # Time properties
    @property
    def sidereal_time(self) -> float:
        """LST in hours."""
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                lst_str = self._onstepx.send_command(':GS#')
                # Parse HH:MM:SS format to decimal hours
                parts = lst_str.split(':')
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = int(parts[2])
                return hours + minutes/60.0 + seconds/3600.0
            except Exception as ex:
                raise DriverException(0x500, f'Failed to get sidereal time: {str(ex)}')

    @property
    def utc_date(self) -> str:
        """UTC date/time in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    @utc_date.setter
    def utc_date(self, value: str):
        """Set UTC date/time."""
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                # Parse ISO format datetime string
                from datetime import datetime
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                self._onstepx.set_utc_date(dt)
            except Exception as ex:
                raise DriverException(0x400, f'Failed to set UTC date: {str(ex)}')

    # Mount properties
    @property
    def alignment_mode(self) -> int:
        """AlignmentMode: 0=AltAz, 1=Polar, 2=GermanPolar."""
        return 2  # Assume German equatorial mount

    @property
    def aperture_area(self) -> float:
        return self._aperture_area

    @property
    def aperture_diameter(self) -> float:
        return self._aperture_diameter

    @property
    def focal_length(self) -> float:
        return self._focal_length

    @property
    def does_refraction(self) -> bool:
        """OnStepX does refraction internally."""
        return True

    @property
    def equatorial_system(self) -> int:
        """EquatorialSystem: 1=equTopocentric."""
        return 1

    # Tracking properties
    @property
    def tracking_rate(self) -> int:
        """TrackingRate: 0=sidereal, 1=lunar, 2=solar, 3=king."""
        return 0  # Default sidereal

    @tracking_rate.setter
    def tracking_rate(self, value: int):
        modes = ['sidereal', 'lunar', 'solar', 'king']
        if 0 <= value < len(modes):
            self._onstepx.set_tracking_mode(modes[value])

    @property
    def tracking_rates(self) -> List[int]:
        """Available tracking rates."""
        return [0, 1, 2, 3]  # sidereal, lunar, solar, king

    @property
    def right_ascension_rate(self) -> float:
        """RA tracking rate offset in arcsec/sidereal-sec."""
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                response = self._onstepx.send_command(':GXTR#')
                return float(response)
            except Exception as ex:
                raise DriverException(0x500, f'Failed to get RA rate: {str(ex)}')

    @right_ascension_rate.setter
    def right_ascension_rate(self, value: float):
        """Set RA tracking rate offset in arcsec/sidereal-sec."""
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                response = self._onstepx.send_command(f':SXTR,{value:.2f}#')
                if response != '1':
                    raise DriverException(0x400, f'Failed to set RA rate: {response}')
            except Exception as ex:
                raise DriverException(0x400, f'Failed to set RA rate: {str(ex)}')

    @property
    def declination_rate(self) -> float:
        """Dec tracking rate offset in arcsec/sec."""
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                response = self._onstepx.send_command(':GXTD#')
                return float(response)
            except Exception as ex:
                raise DriverException(0x500, f'Failed to get Dec rate: {str(ex)}')

    @declination_rate.setter
    def declination_rate(self, value: float):
        """Set Dec tracking rate offset in arcsec/sec."""
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                response = self._onstepx.send_command(f':SXTD,{value:.2f}#')
                if response != '1':
                    raise DriverException(0x400, f'Failed to set Dec rate: {response}')
            except Exception as ex:
                raise DriverException(0x400, f'Failed to set Dec rate: {str(ex)}')

    # Pier side
    @property
    def side_of_pier(self) -> int:
        """SideOfPier: 0=pierEast, 1=pierWest, -1=pierUnknown."""
        with self._lock:
            return self._cached_pier_side

    @property
    def destination_side_of_pier(self) -> int:
        """Destination pier side for slew."""
        # For now, return current side
        return self.side_of_pier

    # Guide rates
    @property
    def guide_rate_right_ascension(self) -> float:
        """RA guide rate as fraction of sidereal.

        OnStepX uses fixed guide rates (1x, 8x, 20x, 48x).
        Return 1.0 (1x sidereal) as the guide rate.
        """
        return 1.0  # OnStepX guide rate is 1x sidereal

    @guide_rate_right_ascension.setter
    def guide_rate_right_ascension(self, value: float):
        """Set RA guide rate.

        OnStepX doesn't support custom guide rates - uses fixed presets.
        This is a no-op for ASCOM compatibility.
        """
        pass  # OnStepX uses fixed rates, not custom values

    @property
    def guide_rate_declination(self) -> float:
        """Dec guide rate as fraction of sidereal.

        OnStepX uses fixed guide rates (1x, 8x, 20x, 48x).
        Return 1.0 (1x sidereal) as the guide rate.
        """
        return 1.0  # OnStepX guide rate is 1x sidereal

    @guide_rate_declination.setter
    def guide_rate_declination(self, value: float):
        """Set Dec guide rate.

        OnStepX doesn't support custom guide rates - uses fixed presets.
        This is a no-op for ASCOM compatibility.
        """
        pass  # OnStepX uses fixed rates, not custom values

    # Capability properties
    @property
    def can_find_home(self) -> bool:
        return True

    @property
    def can_park(self) -> bool:
        return True

    @property
    def can_pulse_guide(self) -> bool:
        return True

    @property
    def can_set_guide_rates(self) -> bool:
        return False

    @property
    def can_set_park(self) -> bool:
        return True

    @property
    def can_set_pier_side(self) -> bool:
        return False

    @property
    def can_set_tracking(self) -> bool:
        return True

    @property
    def can_slew(self) -> bool:
        return True

    @property
    def can_slew_async(self) -> bool:
        return True

    @property
    def can_slew_alt_az(self) -> bool:
        return True

    @property
    def can_slew_alt_az_async(self) -> bool:
        return True

    @property
    def can_sync(self) -> bool:
        return True

    @property
    def can_sync_alt_az(self) -> bool:
        return False

    @property
    def can_unpark(self) -> bool:
        return True

    @property
    def can_move_axis(self) -> bool:
        return False

    # ==================== ASCOM Methods ====================

    def slew_to_coordinates(self, ra: float, dec: float):
        """Slew to RA/Dec (blocking)."""
        self.target_right_ascension = ra
        self.target_declination = dec
        self.slew_to_target()

    def slew_to_coordinates_async(self, ra: float, dec: float):
        """Slew to RA/Dec (non-blocking)."""
        self.target_right_ascension = ra
        self.target_declination = dec
        self.slew_to_target_async()

    def slew_to_target(self):
        """Slew to current target (blocking)."""
        ra, dec = self.target_right_ascension, self.target_declination
        error_code = self._onstepx.goto_radec(ra, dec)
        if error_code != 0:
            self._handle_goto_error(error_code)
        # Wait for slew to complete
        while self.slewing:
            time.sleep(0.5)

    def slew_to_target_async(self):
        """Slew to current target (non-blocking)."""
        ra, dec = self.target_right_ascension, self.target_declination
        error_code = self._onstepx.goto_radec(ra, dec)
        if error_code != 0:
            self._handle_goto_error(error_code)

    def slew_to_alt_az(self, az: float, alt: float):
        """Slew to Alt/Az (blocking)."""
        error_code = self._onstepx.goto_altaz(alt, az)
        if error_code != 0:
            self._handle_goto_error(error_code)
        while self.slewing:
            time.sleep(0.5)

    def slew_to_alt_az_async(self, az: float, alt: float):
        """Slew to Alt/Az (non-blocking)."""
        error_code = self._onstepx.goto_altaz(alt, az)
        if error_code != 0:
            self._handle_goto_error(error_code)

    def _handle_goto_error(self, code: int):
        """Convert OnStepX error code to ASCOM exception."""
        errors = {
            1: 'Below horizon limit',
            2: 'Above overhead limit',
            3: 'Controller in standby',
            4: 'Mount is parked',
            5: 'Goto already in progress',
            6: 'Outside limits',
            7: 'Hardware fault',
            8: 'Already in motion',
            9: 'Unspecified error'
        }
        msg = errors.get(code, f'Error code {code}')
        if code == 4:
            raise ParkedException(msg)
        elif code in [5, 8]:
            raise InvalidOperationException(msg)
        elif code == 6:
            raise InvalidValueException(msg)
        else:
            raise DriverException(0x500, msg)

    def abort_slew(self):
        """Stop all motion."""
        self._onstepx.stop_slew()

    def park(self):
        """Park the mount."""
        self._onstepx.park()
        with self._lock:
            self._cached_at_park = True

    def set_park(self):
        """Set current position as park position."""
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                response = self._onstepx.send_command(':hQ#')
                if response != '1':
                    raise DriverException(0x400, f'Failed to set park position: {response}')
            except Exception as ex:
                raise DriverException(0x400, f'Failed to set park position: {str(ex)}')

    def unpark(self):
        """Unpark the mount."""
        self._onstepx.unpark()
        with self._lock:
            self._cached_at_park = False

    def find_home(self):
        """Find home position."""
        self._onstepx.goto_home()

    def sync_to_coordinates(self, ra: float, dec: float):
        """Sync to RA/Dec coordinates."""
        self.target_right_ascension = ra
        self.target_declination = dec
        self.sync_to_target()

    def sync_to_target(self):
        """Sync to current target."""
        error_code = self._onstepx.sync_to_target()
        if error_code != 0:
            raise DriverException(0x500, f'Sync failed with code {error_code}')

    def sync_to_alt_az(self, az: float, alt: float):
        """Sync to Alt/Az - not supported."""
        raise NotImplementedException('SyncToAltAz not supported')

    def pulse_guide(self, direction: int, duration: int):
        """Pulse guide in direction for duration ms.

        Args:
            direction: 0=North, 1=South, 2=East, 3=West
            duration: Duration in milliseconds
        """
        dirs = ['N', 'S', 'E', 'W']
        if 0 <= direction < 4:
            self._onstepx.pulse_guide(dirs[direction], duration)
            # Track pulse guide state
            with self._lock:
                self._pulse_guide_start = time.time()
                self._pulse_guide_duration = duration
        else:
            raise InvalidValueException(f'Invalid guide direction {direction}')

    def move_axis(self, axis: int, rate: float):
        """Move axis at rate - not implemented."""
        raise NotImplementedException('MoveAxis not supported')
