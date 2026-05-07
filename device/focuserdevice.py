# -*- coding: utf-8 -*-
# =================================================================
# focuserdevice.py - OnStepX Focuser Device Logic Layer
# =================================================================
#
# ASCOM Alpaca focuser device implementation for OnStepX controller
# Wraps OnStepXFocuser with ASCOM IFocuserV4 semantics
# Provides full thread-safe property and method access
#
# Author: Generated for OnStepX
# Python Compatibility: Requires Python 3.7 or later
#
# =================================================================

from logging import Logger
from threading import RLock, Lock
from typing import Optional

try:
    from .onstepx_focuser import OnStepXFocuser
    from .onstepx_device import OnStepXDevice
except ImportError:
    from onstepx_focuser import OnStepXFocuser
    from onstepx_device import OnStepXDevice

from exceptions import (
    NotConnectedException,
    InvalidValueException,
    PropertyNotImplementedException,
    DriverException,
    DriverException as AlpacaDriverException,
)


class FocuserDevice:
    """OnStepX focuser device with ASCOM IFocuserV4 interface.

    Wraps OnStepXFocuser communication layer with ASCOM semantics,
    thread-safe operations, and full property/method support.

    All operations are synchronized via internal locking to ensure
    thread-safe access to the shared OnStepX connection.

    Attributes:
        _logger: Python logger instance
        _lock: Threading lock for synchronization
        _focuser: OnStepXFocuser instance (underlying controller)
        _connected: Connection state flag
        _target_position: Last requested target position
        _temp_comp_available: Cached temperature sensor availability
    """

    def __init__(
        self,
        logger: Logger,
        onstepx_device: OnStepXDevice,
        focuser_number: int = 1
    ):
        """Initialize OnStepX focuser device.

        Args:
            logger: Python logger instance for debug/error logging
            onstepx_device: Shared OnStepXDevice instance for command communication
            focuser_number: Focuser unit number (1-6). Defaults to 1 (primary).

        Raises:
            ValueError: If focuser_number is not in range 1-6
            TypeError: If logger is not a Logger instance
            TypeError: If onstepx_device is not an OnStepXDevice instance
        """
        if not isinstance(logger, Logger):
            raise TypeError('logger must be a Logger instance')
        if not isinstance(onstepx_device, OnStepXDevice):
            raise TypeError('onstepx_device must be an OnStepXDevice instance')
        if not 1 <= focuser_number <= 6:
            raise ValueError(f'focuser_number must be 1-6, got {focuser_number}')

        self.logger = logger
        self._lock = RLock()
        self._focuser = OnStepXFocuser(onstepx_device, logger, focuser_number)
        self._connected = False
        self._target_position = 0
        self._temp_comp_available = None

    # ==================== Connection Management ====================

    def connect(self) -> None:
        """Connect to focuser hardware and verify availability.

        Validates focuser is active and checks temperature sensor availability
        for temp_comp_available property.

        Raises:
            DriverException: If focuser is not active or connection fails
        """
        with self._lock:
            try:
                if not self._focuser.is_active():
                    raise AlpacaDriverException(0x500, 'Focuser not active')

                self._connected = True

                # Check temperature sensor availability
                try:
                    self._focuser.get_temperature()
                    self._temp_comp_available = True
                except (AlpacaDriverException, DriverException):
                    self._temp_comp_available = False

                self.logger.info('Focuser connected')
            except AlpacaDriverException:
                raise
            except Exception as ex:
                raise AlpacaDriverException(0x500, f'Connection failed: {str(ex)}')

    def disconnect(self) -> None:
        """Disconnect from focuser hardware.

        Sets connection state to False. Hardware connection remains
        open for other devices that may share it.
        """
        with self._lock:
            self._connected = False
            self.logger.info('Focuser disconnected')

    # ==================== ASCOM IFocuserV4 Properties ====================

    @property
    def connected(self) -> bool:
        """Get focuser connection state.

        Returns:
            bool: True if connected to focuser hardware, False otherwise
        """
        with self._lock:
            return self._connected

    @property
    def absolute(self) -> bool:
        """Get positioning mode (always True for OnStepX).

        OnStepX focuser uses absolute positioning exclusively.

        Returns:
            bool: True (absolute positioning supported)
        """
        return True

    @property
    def is_moving(self) -> bool:
        """Get current focuser movement state.

        Queries OnStepX for movement status via :FT# command.

        Returns:
            bool: True if focuser is moving, False if stopped

        Raises:
            NotConnectedException: If focuser is not connected
            DriverException: If status query fails
        """
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                return self._focuser.get_is_moving()
            except AlpacaDriverException:
                raise
            except Exception as ex:
                raise AlpacaDriverException(0x500, f'Failed to check movement status: {str(ex)}')

    @property
    def max_increment(self) -> int:
        """Get maximum single move increment.

        For OnStepX, this is typically the full range from zero to max position.
        Returned in microns or steps depending on focuser mode.

        Returns:
            int: Maximum increment in microns or steps

        Raises:
            NotConnectedException: If focuser is not connected
            DriverException: If query fails
        """
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                return self._focuser.get_max_position()
            except AlpacaDriverException:
                raise
            except Exception as ex:
                raise AlpacaDriverException(0x500, f'Failed to get max increment: {str(ex)}')

    @property
    def max_step(self) -> int:
        """Get maximum focuser position.

        The maximum position value for absolute movement commands.
        Returned in microns or steps depending on focuser mode.

        Returns:
            int: Maximum position in microns or steps

        Raises:
            NotConnectedException: If focuser is not connected
            DriverException: If query fails
        """
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                return self._focuser.get_max_position()
            except AlpacaDriverException:
                raise
            except Exception as ex:
                raise AlpacaDriverException(0x500, f'Failed to get max step: {str(ex)}')

    @property
    def position(self) -> int:
        """Get current focuser position.

        Queries OnStepX for current position via :FG# command.
        Position is in microns or steps depending on focuser mode.

        Returns:
            int: Current position in microns or steps

        Raises:
            NotConnectedException: If focuser is not connected
            DriverException: If position query fails
        """
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                return self._focuser.get_position()
            except AlpacaDriverException:
                raise
            except Exception as ex:
                raise AlpacaDriverException(0x500, f'Failed to get position: {str(ex)}')

    @property
    def step_size(self) -> float:
        """Get conversion factor from steps to physical units.

        Returns the number of microns per step, allowing conversion
        between step counts and physical distance.

        Returns:
            float: Microns per step

        Raises:
            NotConnectedException: If focuser is not connected
            DriverException: If query fails
        """
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                return self._focuser.get_microns_per_step()
            except AlpacaDriverException:
                raise
            except Exception as ex:
                raise AlpacaDriverException(0x500, f'Failed to get step size: {str(ex)}')

    @property
    def temp_comp(self) -> bool:
        """Get temperature compensation enabled status.

        Queries OnStepX for compensation state via :Fc# command.

        Returns:
            bool: True if temperature compensation is enabled, False otherwise

        Raises:
            NotConnectedException: If focuser is not connected
            DriverException: If status query fails
        """
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                return self._focuser.get_temp_comp_enabled()
            except AlpacaDriverException:
                raise
            except Exception as ex:
                raise AlpacaDriverException(0x500, f'Failed to get temp comp status: {str(ex)}')

    @temp_comp.setter
    def temp_comp(self, enabled: bool) -> None:
        """Enable or disable temperature compensation.

        Sets temperature compensation state via :Fc[n]# command
        where n=0 (disabled) or n=1 (enabled).

        Args:
            enabled: True to enable, False to disable

        Raises:
            NotConnectedException: If focuser is not connected
            DriverException: If command fails
        """
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                self._focuser.set_temp_comp_enabled(enabled)
            except AlpacaDriverException:
                raise
            except Exception as ex:
                status = 'enable' if enabled else 'disable'
                raise AlpacaDriverException(0x408, f'Failed to {status} temp comp: {str(ex)}')

    @property
    def temp_comp_available(self) -> bool:
        """Check if temperature compensation is available.

        Returns True if focuser has a connected temperature sensor,
        False otherwise. Checked during connect() method.

        Returns:
            bool: True if temperature sensor is available, False otherwise

        Raises:
            NotConnectedException: If focuser is not connected
        """
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            if self._temp_comp_available is None:
                return False
            return self._temp_comp_available

    @property
    def temperature(self) -> float:
        """Get focuser temperature from sensor.

        Queries OnStepX for current temperature via :Ft# command.
        Temperature is in degrees Celsius.

        Returns:
            float: Temperature in degrees Celsius

        Raises:
            NotConnectedException: If focuser is not connected
            PropertyNotImplementedException: If temperature sensor not available
            DriverException: If temperature query fails
        """
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            if not self.temp_comp_available:
                raise PropertyNotImplementedException('Temperature sensor not available')

            try:
                return self._focuser.get_temperature()
            except AlpacaDriverException:
                raise
            except Exception as ex:
                raise AlpacaDriverException(0x500, f'Failed to get temperature: {str(ex)}')

    # ==================== ASCOM IFocuserV4 Methods ====================

    def move(self, position: int) -> None:
        """Move focuser to absolute position.

        Performs absolute positioning via OnStepX :FS# (set target) and
        :FG# (goto target) commands. Position bounds are validated before
        movement is initiated.

        Args:
            position: Target position in microns or steps

        Raises:
            NotConnectedException: If focuser is not connected
            InvalidValueException: If position is negative or exceeds max_step
            DriverException: If movement command fails
        """
        if not self.connected:
            raise NotConnectedException()

        # Validate position bounds
        if position < 0:
            raise InvalidValueException(f'Position {position} < 0')

        max_pos = self.max_step
        if position > max_pos:
            raise InvalidValueException(f'Position {position} > max {max_pos}')

        with self._lock:
            try:
                self._target_position = position
                self._focuser.move_absolute(position)
            except AlpacaDriverException:
                raise
            except Exception as ex:
                raise AlpacaDriverException(0x408, f'Failed to move to position {position}: {str(ex)}')

    def halt(self) -> None:
        """Stop all focuser movement immediately.

        Halts any in-progress movement via OnStepX :FQ# command.

        Raises:
            NotConnectedException: If focuser is not connected
            DriverException: If halt command fails
        """
        if not self.connected:
            raise NotConnectedException()

        with self._lock:
            try:
                self._focuser.halt()
            except AlpacaDriverException:
                raise
            except Exception as ex:
                raise AlpacaDriverException(0x408, f'Failed to halt focuser: {str(ex)}')
