# =================================================================
# ROTATORDEVICE.PY - OnStepX Rotator ASCOM IRotatorV4 Implementation
# =================================================================
#
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# rotatordevice.py - ASCOM IRotatorV4 interface for OnStepX rotator controller
#
# Part of the AlpycaDevice Alpaca skeleton/template device driver
#
# Wraps OnStepXRotator module to provide full ASCOM IRotatorV4 interface.
# Supports mechanical vs sky position with software sync offset.
# Real hardware only - NO SIMULATION.
#
# Author:   Vince Geisler
# Python Compatibility: Requires Python 3.7 or later
# GitHub: https://github.com/ASCOMInitiative/AlpycaDevice
#
# -----------------------------------------------------------------------------
# MIT License
#
# Copyright (c) 2022-2024 Bob Denny
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# -----------------------------------------------------------------------------
# Edit History:
# 06-May-2026   VG      1.0 OnStepX implementation replacing simulator
#

from threading import RLock, Lock
from logging import Logger
from onstepx_rotator import OnStepXRotator
from onstepx_device import OnStepXDevice
from exceptions import NotConnectedException, InvalidOperationException


class RotatorDevice:
    """ASCOM IRotatorV4 implementation for OnStepX rotator controller.

    Provides full ASCOM IRotatorV4 interface wrapping OnStepXRotator
    communication module. Supports:

    - Real hardware movement (no simulation)
    - Absolute, relative, and mechanical position moves
    - Software sync offset (mechanical vs sky position)
    - Derotator reverse control
    - Thread-safe hardware communication

    **Mechanical vs Sky Position**

    The rotator supports both:
    - Sky position: What the user wants (after sync calibration)
    - Mechanical position: Raw hardware position

    These are related by the sync offset: sky = mechanical + offset

    **Sync Offset**

    The sync offset allows calibration of mechanical vs sky coordinates.
    When the user calls sync(position), the current hardware position
    is stored as the given sky position, computing the offset.
    """

    def __init__(self, logger: Logger, onstepx_device: OnStepXDevice):
        """Initialize ASCOM IRotatorV4 device wrapper.

        Args:
            logger: Python logger instance
            onstepx_device: OnStepXDevice instance for hardware communication

        Raises:
            TypeError: If arguments are not correct type
        """
        if not isinstance(logger, Logger):
            raise TypeError('logger must be Logger instance')
        if not isinstance(onstepx_device, OnStepXDevice):
            raise TypeError('onstepx_device must be OnStepXDevice instance')

        self._lock = RLock()
        self.logger = logger
        self._rotator = OnStepXRotator(onstepx_device, logger)
        self._connected = False
        self._pos_offset = 0.0
        self._derotator_reversed = False
        self._target_position = 0.0

        self.logger.info('RotatorDevice initialized')

    # ====================================================================
    # POSITION NORMALIZATION HELPERS
    # ====================================================================

    def _normalize_angle(self, angle: float) -> float:
        """Normalize angle to 0-360 range.

        Args:
            angle: Angle in degrees (may be negative or > 360)

        Returns:
            float: Normalized angle in 0-360 range
        """
        while angle < 0:
            angle += 360
        while angle >= 360:
            angle -= 360
        return angle

    def _pos_to_mech(self, pos: float) -> float:
        """Convert sky position to mechanical position.

        Applies sync offset to convert from user-visible sky position
        to raw mechanical position on the rotator.

        Args:
            pos: Sky position in degrees

        Returns:
            float: Mechanical position in 0-360 range
        """
        mech = pos - self._pos_offset
        return self._normalize_angle(mech)

    def _mech_to_pos(self, mech: float) -> float:
        """Convert mechanical position to sky position.

        Applies sync offset to convert from raw mechanical position
        to user-visible sky position.

        Args:
            mech: Mechanical position in degrees

        Returns:
            float: Sky position in 0-360 range
        """
        pos = mech + self._pos_offset
        return self._normalize_angle(pos)

    # ====================================================================
    # ASCOM IROTATORV4 PROPERTIES
    # ====================================================================

    @property
    def connected(self) -> bool:
        """Get connection status.

        Returns:
            bool: True if connected to hardware, False otherwise
        """
        self._lock.acquire()
        try:
            res = self._connected
            return res
        finally:
            self._lock.release()

    @connected.setter
    def connected(self, value: bool) -> None:
        """Set connection status.

        Args:
            value: True to connect, False to disconnect

        Raises:
            InvalidOperationException: If cannot disconnect while moving
            RuntimeError: If hardware communication fails
        """
        self._lock.acquire()
        try:
            if value == self._connected:
                return

            if value:
                # Connect to hardware
                try:
                    if not self._rotator.is_active():
                        raise RuntimeError('Rotator not active on hardware')
                    self._connected = True
                    self.logger.info('[connected] to rotator')
                except Exception as e:
                    self.logger.error(f'Failed to connect: {str(e)}')
                    raise
            else:
                # Disconnect
                if self.is_moving:
                    raise InvalidOperationException('Cannot disconnect while rotator is moving')
                self._connected = False
                self.logger.info('[disconnected] from rotator')
        finally:
            self._lock.release()

    @property
    def connecting(self) -> bool:
        """Get whether device is currently connecting/disconnecting.

        For OnStepX, connection/disconnection is instantaneous,
        so this always returns False.

        Returns:
            bool: False (connections are synchronous)
        """
        return False

    @property
    def can_reverse(self) -> bool:
        """Get whether rotator supports reverse.

        OnStepX has :rR# derotator reverse command, so always True.

        Returns:
            bool: True (OnStepX always supports reverse)
        """
        return True

    @property
    def is_moving(self) -> bool:
        """Get rotator motion status.

        Queries hardware to determine if rotator is currently moving.

        Returns:
            bool: True if rotator is moving, False if stationary

        Raises:
            NotConnectedException: If not connected
        """
        self._lock.acquire()
        try:
            if not self._connected:
                raise NotConnectedException()
            res = self._rotator.get_is_moving()
            self.logger.debug(f'[is_moving] {res}')
            return res
        finally:
            self._lock.release()

    @property
    def position(self) -> float:
        """Get current sky position (with sync offset applied).

        This is the position in the user's coordinate system, after
        applying the sync offset. Most clients should use this.

        Returns:
            float: Current position in degrees (0-360)

        Raises:
            NotConnectedException: If not connected
        """
        self._lock.acquire()
        try:
            if not self._connected:
                raise NotConnectedException()
            mech = self._rotator.get_position()
            res = self._mech_to_pos(mech)
            self.logger.debug(f'[position] {res:.2f}°')
            return res
        finally:
            self._lock.release()

    @property
    def mechanical_position(self) -> float:
        """Get current mechanical position (raw, no sync offset).

        This is the raw hardware position without any calibration offset.
        Normally clients should use position property instead.

        Returns:
            float: Current mechanical position in degrees (0-360)

        Raises:
            NotConnectedException: If not connected
        """
        self._lock.acquire()
        try:
            if not self._connected:
                raise NotConnectedException()
            res = self._rotator.get_position()
            self.logger.debug(f'[mechanical_position] {res:.2f}°')
            return res
        finally:
            self._lock.release()

    @property
    def reverse(self) -> bool:
        """Get derotator reverse state.

        Tracks whether derotator rotation is reversed. This is software-tracked
        since the underlying :rR# command is a toggle.

        Returns:
            bool: True if derotator is reversed, False if normal

        Raises:
            NotConnectedException: If not connected
        """
        self._lock.acquire()
        try:
            if not self._connected:
                raise NotConnectedException()
            res = self._derotator_reversed
            self.logger.debug(f'[reverse] {res}')
            return res
        finally:
            self._lock.release()

    @reverse.setter
    def reverse(self, value: bool) -> None:
        """Set derotator reverse state.

        Toggles derotator direction if needed to reach desired state.
        The underlying :rR# command toggles, so we track state in software
        to know current state and only toggle if needed.

        Args:
            value: True to reverse, False for normal

        Raises:
            NotConnectedException: If not connected
            RuntimeError: If hardware command fails
        """
        self._lock.acquire()
        try:
            if not self._connected:
                raise NotConnectedException()

            if value != self._derotator_reversed:
                # Need to toggle
                self._rotator.reverse_derotator()
                self._derotator_reversed = value
                self.logger.info(f'[reverse] set to {value}')
        finally:
            self._lock.release()

    @property
    def step_size(self) -> float:
        """Get rotator step size in degrees.

        Returns the mechanical resolution of the rotator hardware.

        Returns:
            float: Degrees per step

        Raises:
            NotConnectedException: If not connected
        """
        self._lock.acquire()
        try:
            if not self._connected:
                raise NotConnectedException()
            res = self._rotator.get_step_size()
            self.logger.debug(f'[step_size] {res:.4f}°')
            return res
        finally:
            self._lock.release()

    @property
    def target_position(self) -> float:
        """Get target sky position.

        Returns the last position specified in a move_absolute() or move() call.
        In sky coordinates (with sync offset applied).

        Returns:
            float: Target position in degrees (0-360)
        """
        self._lock.acquire()
        try:
            res = self._target_position
            self.logger.debug(f'[target_position] {res:.2f}°')
            return res
        finally:
            self._lock.release()

    @target_position.setter
    def target_position(self, value: float) -> None:
        """Set target sky position and move rotator.

        This setter implements IRotatorV4 by immediately starting a move
        to the specified position.

        Args:
            value: Target position in degrees (0-360)

        Raises:
            NotConnectedException: If not connected
            InvalidOperationException: If rotator is already moving
            ValueError: If position is outside valid range
        """
        self._lock.acquire()
        try:
            if not self._connected:
                raise NotConnectedException()
            if value < 0 or value >= 360:
                raise ValueError(f'Position out of range: {value}')
            self.move_absolute(value)
        finally:
            self._lock.release()

    # ====================================================================
    # ASCOM IROTATORV4 METHODS
    # ====================================================================

    def connect(self) -> None:
        """Connect to rotator hardware.

        Validates hardware is present and operational, then sets connected state.

        Raises:
            RuntimeError: If hardware is not active or communication fails
        """
        self.logger.debug('[connect]')
        self.connected = True

    def disconnect(self) -> None:
        """Disconnect from rotator hardware.

        Raises:
            InvalidOperationException: If rotator is moving
        """
        self.logger.debug('[disconnect]')
        self.connected = False

    def move(self, position: float) -> None:
        """Relative move by specified angle.

        Per IRotatorV4 spec, this is a RELATIVE move. The rotator moves
        by the specified amount from the current position.

        Args:
            position: Amount to move in degrees (positive = increase angle)

        Raises:
            NotConnectedException: If not connected
            InvalidOperationException: If rotator is already moving
            RuntimeError: If hardware communication fails
        """
        self.logger.debug(f'[move] relative {position:.2f}°')
        self._lock.acquire()
        try:
            if not self._connected:
                raise NotConnectedException()

            current_sky = self._mech_to_pos(self._rotator.get_position())
            target_sky = current_sky + position
            target_sky = self._normalize_angle(target_sky)

            self.move_absolute(target_sky)
        finally:
            self._lock.release()

    def move_absolute(self, position: float) -> None:
        """Absolute move to sky position.

        Moves rotator to the specified position in the user's coordinate
        system (after applying sync offset). This is the standard move method.

        Args:
            position: Target sky position in degrees (0-360)

        Raises:
            NotConnectedException: If not connected
            InvalidOperationException: If rotator is already moving
            ValueError: If position is outside valid range
            RuntimeError: If hardware communication fails
        """
        self.logger.debug(f'[move_absolute] sky position {position:.2f}°')
        self._lock.acquire()
        try:
            if not self._connected:
                raise NotConnectedException()

            if position < 0 or position >= 360:
                raise ValueError(f'Position out of range: {position}')

            # Store target in sky coordinates
            self._target_position = position

            # Convert to mechanical coordinates
            mech_target = self._pos_to_mech(position)

            # Command hardware (may raise InvalidOperationException if already moving)
            self._rotator.move_absolute(mech_target)

            self.logger.info(f'Moving to {position:.2f}° (mechanical: {mech_target:.2f}°)')
        finally:
            self._lock.release()

    def move_mechanical(self, position: float) -> None:
        """Absolute move to mechanical position.

        Moves to the specified mechanical position WITHOUT applying sync offset.
        Useful for low-level hardware testing.

        Args:
            position: Target mechanical position in degrees (0-360)

        Raises:
            NotConnectedException: If not connected
            InvalidOperationException: If rotator is already moving
            ValueError: If position is outside valid range
            RuntimeError: If hardware communication fails
        """
        self.logger.debug(f'[move_mechanical] mechanical position {position:.2f}°')
        self._lock.acquire()
        try:
            if not self._connected:
                raise NotConnectedException()

            if position < 0 or position >= 360:
                raise ValueError(f'Position out of range: {position}')

            # Normalize
            position = self._normalize_angle(position)

            # Store target (converting back to sky for consistency)
            self._target_position = self._mech_to_pos(position)

            # Command hardware (may raise InvalidOperationException if already moving)
            self._rotator.move_absolute(position)

            self.logger.info(f'Moving to mechanical position {position:.2f}°')
        finally:
            self._lock.release()

    def halt(self) -> None:
        """Stop all rotator motion.

        Raises:
            NotConnectedException: If not connected
            RuntimeError: If hardware communication fails
        """
        self.logger.debug('[halt]')
        self._lock.acquire()
        try:
            if not self._connected:
                raise NotConnectedException()
            self._rotator.halt()
            self.logger.info('Rotator halted')
        finally:
            self._lock.release()

    def sync(self, position: float) -> None:
        """Sync current position to specified sky angle.

        Calibrates the rotator by declaring that the current mechanical
        position should be treated as the given sky position. This computes
        and stores the sync offset.

        Args:
            position: Current sky position in degrees (0-360)

        Raises:
            NotConnectedException: If not connected
            InvalidOperationException: If rotator is moving
            ValueError: If position is outside valid range
            RuntimeError: If hardware communication fails
        """
        self.logger.debug(f'[sync] to {position:.2f}°')
        self._lock.acquire()
        try:
            if not self._connected:
                raise NotConnectedException()

            if self.is_moving:
                raise InvalidOperationException('Cannot sync while rotator is moving')

            if position < 0 or position >= 360:
                raise ValueError(f'Position out of range: {position}')

            # Get current mechanical position
            mech = self._rotator.get_position()

            # Compute new sync offset: mech = position - offset, so offset = position - mech
            # But we need to handle angle wrapping correctly
            self._pos_offset = position - mech

            # Normalize offset to handle angle wrapping
            self._pos_offset = self._normalize_angle(self._pos_offset)

            # Special handling for near-180 offsets to choose shorter wrap
            if self._pos_offset > 180:
                self._pos_offset -= 360

            self.logger.info(f'Synced: mechanical {mech:.2f}° = sky {position:.2f}° (offset: {self._pos_offset:.2f}°)')
        finally:
            self._lock.release()
