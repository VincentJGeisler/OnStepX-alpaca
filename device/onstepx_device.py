# -*- coding: utf-8 -*-
# =================================================================
# onstepx_device.py - Low-level OnStepX serial/TCP communication
# =================================================================
#
# Low-level driver for OnStepX telescope controller communication
# Handles serial (pySerial) and TCP (WiFi) connections
# Thread-safe command sending and response parsing
#
# Author: Vince Geisler
# Python Compatibility: Requires Python 3.7 or later
#
# =================================================================

import threading
import time
import logging
from logging import Logger
import re
import select
import socket
from typing import Tuple, Optional
from enum import Enum

try:
    import serial
except ImportError:
    serial = None


class ConnectionType(Enum):
    """Supported connection types to OnStepX hardware"""
    SERIAL = 'serial'
    TCP = 'tcp'


class OnStepXDevice:
    """Low-level OnStepX telescope controller communication driver.

    Handles all serial/TCP communication with OnStepX hardware using the
    standard colon-command format (`:CMD#`). Provides thread-safe operations
    with proper locking, error handling, and connection validation.

    Attributes:
        connection_type: 'serial' or 'tcp'
        port: Serial port name (e.g., '/dev/ttyUSB0', 'COM3')
        baud: Serial baud rate (default 9600)
        timeout: Command timeout in seconds
        tcp_host: IP address for TCP connections
        tcp_port: Port for TCP connections
    """

    def __init__(
        self,
        logger: Logger,
        port: str = '/dev/ttyUSB0',
        baud: int = 9600,
        timeout: float = 2.0,
        connection_type: str = 'serial',
        tcp_host: str = None,
        tcp_port: int = None
    ):
        """Initialize OnStepX device connection.

        Args:
            logger: Python logger instance
            port: Serial port name (for serial connections)
            baud: Baud rate for serial communication
            timeout: Command timeout in seconds
            connection_type: 'serial' or 'tcp'
            tcp_host: IP address for TCP connections
            tcp_port: Port for TCP connections
        """
        self.logger = logger
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.connection_type = ConnectionType(connection_type)
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port

        self._lock = threading.Lock()
        self._connected = False
        self._conn = None

        # TCP timing parameters for robust operation over any network
        self._first_byte_timeout = 2.0   # Max wait for first response byte
        self._inter_byte_timeout = 0.5   # Max gap between TCP segments
        self._total_timeout = 5.0        # Hard upper bound for any command
        self._reconnect_delay = 0.5      # Pause before reconnect attempt
        self._max_retries = 1            # Retries on connection loss

    def connect(self) -> bool:
        """Connect to OnStepX hardware and validate connection.

        Establishes either serial or TCP connection and validates by querying
        the product name (`:GVP#`), which must contain "On-Step".

        Returns:
            bool: True if connection successful and validated, False otherwise

        Raises:
            RuntimeError: If connection fails or product validation fails
        """
        with self._lock:
            if self._connected:
                self.logger.debug('Already connected')
                return True

            try:
                if self.connection_type == ConnectionType.SERIAL:
                    self._connect_serial()
                else:
                    self._connect_tcp()

                # Validate connection by querying product name
                product = self._send_command_unsafe(':GVP#')
                if product and 'On-Step' in product:
                    self._connected = True
                    self.logger.info(f'Connected to {product}')
                    return True
                else:
                    raise RuntimeError(f'Product validation failed: {product}')

            except Exception as e:
                self.logger.error(f'Connection failed: {str(e)}')
                self._connected = False
                if self._conn:
                    try:
                        if self.connection_type == ConnectionType.SERIAL:
                            self._conn.close()
                        else:
                            self._conn.close()
                    except:
                        pass
                    self._conn = None
                raise

    def _connect_serial(self) -> None:
        """Establish serial connection to OnStepX."""
        if serial is None:
            raise RuntimeError('pySerial not installed. Install with: pip install pyserial')

        self._conn = serial.Serial(
            port=self.port,
            baudrate=self.baud,
            timeout=self.timeout,
            write_timeout=self.timeout
        )
        self.logger.debug(f'Serial connection opened: {self.port} @ {self.baud} baud')

    def _connect_tcp(self) -> None:
        """Establish TCP connection to OnStepX with keepalive for fragile WiFi.

        Socket configuration rationale:
        - TCP_NODELAY: Disables Nagle's algorithm. Commands are small (<20 bytes)
          and we need them sent immediately, not buffered.
        - SO_KEEPALIVE: Detects dead connections on idle WiFi links.
        - setblocking(True): Correct for use with select(). select() handles the
          waiting/multiplexing; recv() then returns immediately since select()
          already confirmed data is available. Non-blocking mode is NOT needed
          and would complicate error handling with EAGAIN/EWOULDBLOCK.
        - NO SO_SNDBUF override: Let the OS manage send buffer size. Artificially
          small buffers (e.g., 256) can cause sendall() to fragment tiny commands
          into multiple TCP segments, confusing simple embedded TCP stacks.
        - NO SO_LINGER: Let the OS handle connection teardown gracefully.
        """
        self._conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Enable TCP keepalive for fragile WiFi connections
        self._conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        # Platform-specific keepalive tuning
        try:
            # macOS/BSD
            if hasattr(socket, 'TCP_KEEPALIVE'):
                self._conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, 10)
            # Linux
            if hasattr(socket, 'TCP_KEEPIDLE'):
                self._conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 10)
                self._conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
                self._conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        except Exception as e:
            self.logger.debug(f'Could not set keepalive options: {e}')

        # Disable Nagle's algorithm - send commands immediately
        self._conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        # Blocking mode is correct for select()-based I/O
        self._conn.setblocking(True)

        self._conn.connect((self.tcp_host, self.tcp_port))
        self.logger.debug(f'TCP connection opened: {self.tcp_host}:{self.tcp_port} (keepalive enabled)')

    def disconnect(self) -> None:
        """Disconnect from OnStepX hardware.

        Safely closes the connection and marks device as disconnected.
        """
        with self._lock:
            if not self._connected:
                self.logger.debug('Already disconnected')
                return

            try:
                if self._conn:
                    self._conn.close()
                    self.logger.debug('Connection closed')
            except Exception as e:
                self.logger.warning(f'Error closing connection: {str(e)}')
            finally:
                self._conn = None
                self._connected = False

    def send_command(self, cmd: str) -> str:
        """Send a command to OnStepX and get response (thread-safe).

        Commands should be provided with the leading colon (`:`) but without
        the trailing `#`. The method adds the `#` if missing and handles
        the response terminator.

        Args:
            cmd: Command string (e.g., 'GR' or ':GR')

        Returns:
            str: Response from OnStepX with `#` terminator removed

        Raises:
            RuntimeError: If not connected or command fails
        """
        with self._lock:
            if not self._connected:
                raise RuntimeError('Not connected to OnStepX')
            return self._send_command_unsafe(cmd)

    def _send_command_unsafe(self, cmd: str) -> str:
        """Send command without locking (assumes caller holds lock).

        Args:
            cmd: Command string

        Returns:
            str: Response with `#` terminator removed
        """
        # Normalize command format
        if not cmd.startswith(':'):
            cmd = ':' + cmd
        if not cmd.endswith('#'):
            cmd = cmd + '#'

        self.logger.debug(f'-> {cmd}')

        for attempt in range(1 + self._max_retries):
            try:
                if self.connection_type == ConnectionType.SERIAL:
                    response = self._serial_read_response(cmd)
                else:
                    response = self._tcp_read_response(cmd)

                self.logger.debug(f'<- {response}')
                return response

            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError) as e:
                # Connection error - reconnect and retry
                if 'Connection closed' in str(e) or 'Socket in exceptional state' in str(e):
                    is_conn_error = True
                else:
                    is_conn_error = isinstance(e, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError))

                if is_conn_error and attempt < self._max_retries:
                    self.logger.warning(
                        f'Connection lost ({type(e).__name__}: {e}), '
                        f'reconnecting (attempt {attempt + 1})...'
                    )
                    self._reconnect()
                    self.logger.debug(f'-> {cmd} (retry)')
                else:
                    self.logger.error(f'Command failed after retry: {cmd}')
                    raise

            except TimeoutError as e:
                # Timeout is NOT a connection issue - don't reconnect
                self.logger.warning(f'Timeout for {cmd}: {e}')
                raise

        raise RuntimeError(f'Command failed: {cmd}')

    def _reconnect(self) -> None:
        """Close and re-establish the TCP/serial connection."""
        try:
            if self._conn:
                self._conn.close()
        except Exception:
            pass
        self._conn = None

        time.sleep(self._reconnect_delay)

        if self.connection_type == ConnectionType.TCP:
            self._connect_tcp()
        else:
            self._connect_serial()

    def _serial_read_response(self, cmd: str) -> str:
        """Send command via serial and read response.

        Args:
            cmd: Formatted command string

        Returns:
            str: Response without terminator
        """
        self._conn.reset_input_buffer()
        self._conn.reset_output_buffer()
        self._conn.write(cmd.encode('utf-8'))

        response = b''
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            if self._conn.in_waiting > 0:
                byte = self._conn.read(1)
                if byte == b'#':
                    break
                response += byte
            else:
                time.sleep(0.01)

        return response.decode('utf-8', errors='ignore').strip()

    def _tcp_read_response(self, cmd: str) -> str:
        """Send command via TCP and read '#'-terminated response.

        Uses select() for efficient waiting with proper handling of the case
        where OnStepX closes the connection after responding to action commands
        (e.g., :T+#, :hR#). The key insight: when the controller sends a
        response and then closes the connection, recv() may return the response
        data AND empty bytes in quick succession. We must read response data
        BEFORE checking for connection closure.

        Args:
            cmd: Formatted command string

        Returns:
            str: Response without '#' terminator

        Raises:
            OSError: If connection closes before any response data arrives
            TimeoutError: If no response within first_byte_timeout
        """
        self._conn.sendall(cmd.encode('utf-8'))

        response = b''
        start_time = time.monotonic()

        while True:
            elapsed = time.monotonic() - start_time

            # Determine appropriate timeout for this iteration
            if not response:
                # Waiting for first byte - use first_byte_timeout
                wait = self._first_byte_timeout - elapsed
            else:
                # Have partial response - use inter-byte timeout
                wait = self._inter_byte_timeout

            # Check hard deadline
            remaining = self._total_timeout - elapsed
            if remaining <= 0:
                break
            wait = min(wait, remaining)

            if wait <= 0:
                break

            readable, _, exceptional = select.select(
                [self._conn], [], [self._conn], wait
            )

            if exceptional:
                raise OSError('Socket in exceptional state')

            if not readable:
                # Timeout waiting for data
                if not response:
                    raise TimeoutError(
                        f'No response from controller within '
                        f'{self._first_byte_timeout}s for cmd: {cmd}'
                    )
                # Had partial data but no more coming - break and use what we have
                break

            # Socket is readable - either data available or connection closed
            chunk = self._conn.recv(1024)

            if chunk:
                response += chunk
                if b'#' in response:
                    break
            else:
                # recv() returned empty: peer closed connection.
                # This is EXPECTED for action commands (:T+#, :hR#, etc.)
                # that respond and then close. If we already have response
                # data, that's fine - use it. If not, it's a real error.
                if response:
                    # Got data before close - normal for action commands.
                    # Proactively reconnect so next command doesn't fail.
                    self.logger.debug(
                        f'Peer closed after response for {cmd} '
                        f'(got {len(response)} bytes), reconnecting'
                    )
                    try:
                        self._reconnect()
                    except Exception as e:
                        self.logger.warning(
                            f'Proactive reconnect failed: {e} '
                            f'(will retry on next command)'
                        )
                    break
                else:
                    # Closed before sending anything - actual connection loss
                    raise OSError(
                        f'Connection closed by peer before response for {cmd}'
                    )

        # Extract response up to first '#'
        response_str = response.decode('utf-8', errors='ignore')
        if '#' in response_str:
            response_str = response_str.split('#')[0]

        return response_str.strip()

    # ====================================================================
    # POSITION AND STATUS COMMANDS
    # ====================================================================

    def get_position(self) -> Tuple[float, float]:
        """Get current mount position in equatorial coordinates.

        Returns:
            Tuple[float, float]: (RA in hours, Dec in degrees)
                RA: 0-24 hours
                Dec: -90 to +90 degrees
        """
        with self._lock:
            ra_str = self._send_command_unsafe(':GRH#')
            dec_str = self._send_command_unsafe(':GDH#')

        ra_hours = hms_to_hours(ra_str)
        dec_degrees = dms_to_degrees(dec_str)

        return (ra_hours, dec_degrees)

    def get_alt_az(self) -> Tuple[float, float]:
        """Get current mount position in horizontal coordinates.

        Returns:
            Tuple[float, float]: (Altitude in degrees, Azimuth in degrees)
                Altitude: -90 to +90 degrees
                Azimuth: 0 to 360 degrees
        """
        with self._lock:
            alt_str = self._send_command_unsafe(':GAH#')
            az_str = self._send_command_unsafe(':GZH#')

        alt_degrees = dms_to_degrees(alt_str)
        az_degrees = dms_to_degrees(az_str)

        return (alt_degrees, az_degrees)

    def get_status(self) -> str:
        """Get telescope combined status (long form).

        Returns the :GU# status string containing tracking, parking,
        slewing, and home state information.

        Returns:
            str: Status string from :GU# command
        """
        return self.send_command(':GU#')

    def get_pier_side(self) -> str:
        """Get pier side/meridian status.

        Returns the primary method result from :Gm# (E/W/N).

        Returns:
            str: 'E' for East, 'W' for West, 'N' for None/Unknown
        """
        response = self.send_command(':Gm#')
        if response == 'E':
            return 'E'
        elif response == 'W':
            return 'W'
        else:
            return 'N'

    def is_slewing(self) -> bool:
        """Check if telescope is currently moving.

        Uses :D# command which returns 0x7F if moving, empty string if stopped.

        Returns:
            bool: True if telescope is moving, False otherwise
        """
        response = self.send_command(':D#')
        return '\x7F' in response

    def stop_slew(self) -> None:
        """Stop all telescope motion.

        Halts slewing, guiding, and any other movement.
        """
        self.send_command(':Q#')
        self.logger.info('Slew stopped')

    # ====================================================================
    # TARGET SETTING AND GOTO COMMANDS
    # ====================================================================

    def set_target_radec(self, ra: float, dec: float) -> bool:
        """Set target coordinates in equatorial coordinates.

        Sets the target RA and Dec for subsequent goto operation.

        Args:
            ra: Right Ascension in hours (0-24)
            dec: Declination in degrees (-90 to +90)

        Returns:
            bool: True if both commands succeeded

        Raises:
            RuntimeError: If coordinates are out of range
        """
        if not (0 <= ra <= 24):
            raise RuntimeError(f'RA out of range: {ra}')
        if not (-90 <= dec <= 90):
            raise RuntimeError(f'Dec out of range: {dec}')

        with self._lock:
            ra_str = hours_to_hms(ra)
            dec_str = degrees_to_dms(dec, is_altitude=False)

            ra_result = self._send_command_unsafe(f':Sr{ra_str}#')
            dec_result = self._send_command_unsafe(f':Sd{dec_str}#')

        success = ra_result == '1' and dec_result == '1'
        if success:
            self.logger.debug(f'Target set: RA={ra:.4f}h, Dec={dec:.4f}°')
        else:
            self.logger.warning(f'Target set failed: RA={ra_result}, Dec={dec_result}')

        return success

    def set_target_altaz(self, alt: float, az: float) -> bool:
        """Set target coordinates in horizontal coordinates.

        Args:
            alt: Altitude in degrees (-90 to +90)
            az: Azimuth in degrees (0 to 360)

        Returns:
            bool: True if both commands succeeded
        """
        if not (-90 <= alt <= 90):
            raise RuntimeError(f'Altitude out of range: {alt}')
        if not (0 <= az <= 360):
            raise RuntimeError(f'Azimuth out of range: {az}')

        with self._lock:
            alt_str = degrees_to_dms(alt, is_altitude=True)
            az_str = degrees_to_dms(az, is_altitude=False)

            alt_result = self._send_command_unsafe(f':Sa{alt_str}#')
            az_result = self._send_command_unsafe(f':Sz{az_str}#')

        success = alt_result == '1' and az_result == '1'
        return success

    def goto_radec(self, ra: float, dec: float) -> int:
        """Slew to target equatorial coordinates.

        Sets target RA/Dec and initiates goto operation.

        Args:
            ra: Right Ascension in hours (0-24)
            dec: Declination in degrees (-90 to +90)

        Returns:
            int: Error code (0 = success)
                 1 = Below horizon limit
                 2 = Above overhead limit
                 3 = Controller in standby
                 4 = Mount is parked
                 5 = Goto in progress
                 6 = Outside limits
                 7 = Hardware fault
                 8 = Already in motion
                 9 = Unspecified error

        Raises:
            RuntimeError: If not connected or coordinates invalid
        """
        self.set_target_radec(ra, dec)
        response = self.send_command(':MS#')

        try:
            error_code = int(response)
        except ValueError:
            self.logger.error(f'Invalid :MS# response: {response}')
            error_code = 9

        if error_code == 0:
            self.logger.info(f'Slewing to RA={ra:.4f}h, Dec={dec:.4f}°')
        else:
            self.logger.warning(f'Goto failed with error code: {error_code}')

        return error_code

    def goto_altaz(self, alt: float, az: float) -> int:
        """Slew to target horizontal coordinates.

        Args:
            alt: Altitude in degrees
            az: Azimuth in degrees

        Returns:
            int: Error code (0 = success)
        """
        self.set_target_altaz(alt, az)
        response = self.send_command(':MA#')

        try:
            error_code = int(response)
        except ValueError:
            error_code = 9

        return error_code

    # ====================================================================
    # TRACKING COMMANDS
    # ====================================================================

    def set_tracking(self, enabled: bool) -> bool:
        """Enable or disable telescope tracking.

        Args:
            enabled: True to enable tracking, False to disable

        Returns:
            bool: True if command succeeded
        """
        cmd = ':T+#' if enabled else ':T-#'
        response = self.send_command(cmd)
        success = response == '1'

        if success:
            self.logger.info(f'Tracking {"enabled" if enabled else "disabled"}')

        return success

    def get_tracking_rate(self) -> float:
        """Get current tracking rate in Hz.

        Returns:
            float: Tracking rate in Hz (0 if not tracking)
        """
        response = self.send_command(':GT#')
        try:
            return float(response)
        except ValueError:
            return 0.0

    def set_tracking_mode(self, mode: str) -> bool:
        """Set tracking rate mode.

        Args:
            mode: 'sidereal', 'lunar', 'solar', or 'king'

        Returns:
            bool: True if command succeeded
        """
        mode_lower = mode.lower()
        if mode_lower == 'sidereal':
            cmd = ':TQ#'
        elif mode_lower == 'lunar':
            cmd = ':TL#'
        elif mode_lower == 'solar':
            cmd = ':TS#'
        elif mode_lower == 'king':
            cmd = ':TK#'
        else:
            raise ValueError(f'Unknown tracking mode: {mode}')

        response = self.send_command(cmd)
        return response == '1'

    # ====================================================================
    # PARK AND HOME COMMANDS
    # ====================================================================

    def park(self) -> bool:
        """Move telescope to park position.

        Returns:
            bool: True if park command accepted, False otherwise
        """
        response = self.send_command(':hP#')
        success = response == '1'
        if success:
            self.logger.info('Park command sent')
        return success

    def unpark(self) -> bool:
        """Restore parked telescope to operation.

        Returns:
            bool: True if unpark succeeded
        """
        response = self.send_command(':hR#')
        success = response == '1'
        if success:
            self.logger.info('Unparked')
        return success

    def goto_home(self) -> bool:
        """Move telescope to home position.

        Returns:
            bool: True if command accepted
        """
        response = self.send_command(':hC#')
        success = response == '1'
        if success:
            self.logger.info('Home command sent')
        return success

    def set_home(self) -> bool:
        """Set current position as home.

        This must be called after a cold start before other operations.

        Returns:
            bool: True if command succeeded
        """
        response = self.send_command(':hF#')
        success = response == '1'
        if success:
            self.logger.info('Home position set')
        return success

    # ====================================================================
    # SITE LOCATION COMMANDS
    # ====================================================================

    def get_site_location(self) -> Tuple[float, float, float]:
        """Get site location (latitude, longitude, elevation).

        Note: OnStepX uses east-negative convention. This method returns
        ASCOM standard with east-positive (negates the longitude).

        Returns:
            Tuple[float, float, float]: (latitude in degrees, longitude in degrees, elevation in meters)
                Latitude: -90 to +90 (South negative)
                Longitude: -180 to +180 (East positive, ASCOM convention)
                Elevation: In meters above sea level
        """
        with self._lock:
            lat_str = self._send_command_unsafe(':GtH#')
            lon_str = self._send_command_unsafe(':GgH#')
            elev_str = self._send_command_unsafe(':Gv#')

        lat = dms_to_degrees(lat_str)
        # OnStepX: east-negative, need to negate to ASCOM: east-positive
        lon_onstepx = dms_to_degrees(lon_str)
        lon = -lon_onstepx

        try:
            elevation = float(elev_str)
        except ValueError:
            elevation = 0.0

        return (lat, lon, elevation)

    def set_site_location(self, lat: float, lon: float, elev: float) -> bool:
        """Set site location.

        Note: Longitude is expected in ASCOM convention (east-positive).
        This method converts to OnStepX convention (east-negative) before sending.

        Args:
            lat: Latitude in degrees (-90 to +90)
            lon: Longitude in degrees (-180 to +180, east-positive)
            elev: Elevation in meters

        Returns:
            bool: True if all commands succeeded
        """
        if not (-90 <= lat <= 90):
            raise ValueError(f'Latitude out of range: {lat}')
        if not (-180 <= lon <= 180):
            raise ValueError(f'Longitude out of range: {lon}')

        with self._lock:
            lat_str = degrees_to_dms(lat, is_altitude=False)
            # Convert ASCOM (east-positive) to OnStepX (east-negative)
            lon_onstepx = -lon
            lon_str = degrees_to_dms(lon_onstepx, is_altitude=False)

            lat_result = self._send_command_unsafe(f':St{lat_str}#')
            lon_result = self._send_command_unsafe(f':Sg{lon_str}#')
            elev_result = self._send_command_unsafe(f':Sv{int(elev)}#')

        success = lat_result == '1' and lon_result == '1' and elev_result == '1'
        if success:
            self.logger.info(f'Site location set: Lat={lat:.4f}°, Lon={lon:.4f}°, Elev={elev:.1f}m')
        return success

    # ====================================================================
    # TIME/DATE COMMANDS
    # ====================================================================

    def get_utc_date(self) -> 'datetime.datetime':
        """Get OnStepX UTC date and time.

        Returns:
            datetime.datetime: Current UTC date/time from OnStepX
        """
        import datetime
        with self._lock:
            date_str = self._send_command_unsafe(':GC#')  # MM/DD/YY
            time_str = self._send_command_unsafe(':GL#')  # HH:MM:SS

        # Parse date MM/DD/YY
        month, day, year = date_str.split('/')
        year = 2000 + int(year)  # YY to YYYY

        # Parse time HH:MM:SS
        hour, minute, second = time_str.split(':')

        return datetime.datetime(
            int(year), int(month), int(day),
            int(hour), int(minute), int(second),
            tzinfo=datetime.timezone.utc
        )

    def set_utc_date(self, dt: 'datetime.datetime') -> bool:
        """Set OnStepX UTC date and time.

        Args:
            dt: datetime object with UTC time

        Returns:
            bool: True if both commands succeeded
        """
        with self._lock:
            # Set date :SC[MM/DD/YY]#
            date_cmd = f':SC{dt.month:02d}/{dt.day:02d}/{dt.year % 100:02d}#'
            date_result = self._send_command_unsafe(date_cmd)

            # Set time :SL[HH:MM:SS]#
            time_cmd = f':SL{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}#'
            time_result = self._send_command_unsafe(time_cmd)

        success = date_result == '1' and time_result == '1'
        if success:
            self.logger.info(f'OnStepX time set to {dt.isoformat()}')
        return success

    # ====================================================================
    # PULSE GUIDE COMMANDS
    # ====================================================================

    def pulse_guide(self, direction: str, duration_ms: int) -> bool:
        """Send pulse guide command for calibration or guiding.

        Args:
            direction: 'N', 'S', 'E', or 'W'
            duration_ms: Pulse duration in milliseconds

        Returns:
            bool: True if command accepted

        Raises:
            ValueError: If direction is invalid or duration out of range
        """
        if direction not in ['N', 'S', 'E', 'W']:
            raise ValueError(f'Invalid guide direction: {direction}')
        if not (0 < duration_ms <= 32767):
            raise ValueError(f'Pulse duration out of range: {duration_ms}')

        # Map directions to axes
        if direction in ['N', 'S']:
            # Dec axis
            cmd_char = 'd'
        else:
            # RA axis
            cmd_char = 'r'

        cmd = f':Mg{cmd_char}{duration_ms}#'
        response = self.send_command(cmd)

        return response == '' or response == '1'

    # ====================================================================
    # SYNC COMMANDS
    # ====================================================================

    def sync_to_target(self) -> int:
        """Sync telescope to current target coordinates.

        Must have set target RA/Dec with set_target_radec() first.
        Uses :CM# command for sync-to-target operation.

        Returns:
            int: Error code (0 = success, 'N/A' response)
                 Other values are error codes 1-9

        Raises:
            RuntimeError: If not connected
        """
        response = self.send_command(':CM#')

        if response == 'N/A' or response == 'NA':
            self.logger.info('Sync to target completed')
            return 0

        try:
            # Check if it starts with 'E' (error code format)
            if response.startswith('E'):
                error_code = int(response[1:])
            else:
                error_code = int(response)
        except ValueError:
            self.logger.warning(f'Unexpected :CM# response: {response}')
            error_code = 9

        if error_code != 0:
            self.logger.warning(f'Sync to target failed with error: {error_code}')

        return error_code

    # ====================================================================
    # SYSTEM INFO COMMANDS
    # ====================================================================

    def get_version(self) -> str:
        """Get OnStepX firmware version number.

        Returns:
            str: Version string (e.g., '10.27l')
        """
        return self.send_command(':GVN#')

    def get_product_name(self) -> str:
        """Get OnStepX product name.

        Returns:
            str: Product name (should contain 'On-Step')
        """
        return self.send_command(':GVP#')

    def get_firmware_message(self) -> str:
        """Get firmware message with version info.

        Returns:
            str: Message string (e.g., 'On-Step 10.27l')
        """
        return self.send_command(':GVM#')


# ============================================================================
# COORDINATE CONVERSION HELPER FUNCTIONS
# ============================================================================

def hms_to_hours(hms: str) -> float:
    """Convert HMS string to decimal hours.

    OnStepX format: "HH:MM:SS.SSSS"

    Args:
        hms: HMS string in format "HH:MM:SS" or "HH:MM:SS.SSSS"

    Returns:
        float: Decimal hours (0-24)

    Raises:
        ValueError: If format is invalid
    """
    hms = hms.strip()
    parts = hms.split(':')

    if len(parts) != 3:
        raise ValueError(f'Invalid HMS format: {hms}')

    try:
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
    except ValueError:
        raise ValueError(f'Invalid HMS format: {hms}')

    total_hours = hours + minutes / 60.0 + seconds / 3600.0
    return total_hours


def dms_to_degrees(dms: str) -> float:
    """Convert DMS string to decimal degrees.

    OnStepX format: "sDD*MM:SS.SSS" (colon before seconds)
    or "sDD*MM'SS.SSS" (apostrophe for arcminutes)

    Args:
        dms: DMS string with sign prefix

    Returns:
        float: Decimal degrees

    Raises:
        ValueError: If format is invalid
    """
    dms = dms.strip()

    # Handle sign
    sign = 1.0
    if dms.startswith('-'):
        sign = -1.0
        dms = dms[1:]
    elif dms.startswith('+'):
        dms = dms[1:]

    # Replace common separators
    dms = dms.replace('*', ' ').replace(':', ' ').replace("'", ' ')

    parts = dms.split()

    if len(parts) < 1:
        raise ValueError(f'Invalid DMS format: {dms}')

    try:
        degrees = float(parts[0])
        minutes = float(parts[1]) if len(parts) > 1 else 0.0
        seconds = float(parts[2]) if len(parts) > 2 else 0.0
    except ValueError:
        raise ValueError(f'Invalid DMS format: {dms}')

    total_degrees = sign * (degrees + minutes / 60.0 + seconds / 3600.0)
    return total_degrees


def hours_to_hms(hours: float) -> str:
    """Convert decimal hours to HMS string.

    Args:
        hours: Decimal hours (0-24)

    Returns:
        str: HMS string in format "HH:MM:SS.SSSS"

    Raises:
        ValueError: If hours out of range
    """
    if not (0 <= hours < 24):
        raise ValueError(f'Hours out of range: {hours}')

    h = int(hours)
    remainder = (hours - h) * 60.0
    m = int(remainder)
    s = (remainder - m) * 60.0

    return f'{h:02d}:{m:02d}:{s:06.3f}'


def degrees_to_dms(degrees: float, is_altitude: bool = False) -> str:
    """Convert decimal degrees to DMS string.

    Args:
        degrees: Decimal degrees
        is_altitude: If True, uses * for arcminutes (alt format),
                    if False, uses : (standard format)

    Returns:
        str: DMS string in format "sDD*MM:SS.SSS" or "sDD*MM'SS.SSS"

    Raises:
        ValueError: If degrees out of range
    """
    if not (-90 <= degrees <= 360):
        raise ValueError(f'Degrees out of range: {degrees}')

    sign_str = '-' if degrees < 0 else '+'
    degrees = abs(degrees)

    d = int(degrees)
    remainder = (degrees - d) * 60.0
    m = int(remainder)
    s = (remainder - m) * 60.0

    # Use appropriate separator for arcminutes
    sep = '*' if is_altitude else '*'
    sec_sep = "'" if is_altitude else ':'

    return f'{sign_str}{d:02d}{sep}{m:02d}{sec_sep}{s:06.3f}'
