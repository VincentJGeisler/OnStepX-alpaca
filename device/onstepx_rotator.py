# -*- coding: utf-8 -*-
# =================================================================
# onstepx_rotator.py - OnStepX rotator control module
# =================================================================
#
# OnStepX rotator-specific command implementation.
# Shares connection with OnStepXDevice (telescope).
# Implements all rotator commands with full error handling.
#
# Author: Vince Geisler
# Python Compatibility: Requires Python 3.7 or later
#
# =================================================================

import re
from logging import Logger
from typing import Optional
from onstepx_device import OnStepXDevice


class OnStepXRotator:
    """OnStepX rotator control module.

    Provides rotator-specific command interface for OnStepX controller.
    Shares connection with telescope OnStepXDevice instance for thread safety.

    All position values are in decimal degrees, normalized to 0-360 range.
    All DMS operations use sDDD*MM format for OnStepX compatibility.
    """

    def __init__(self, device: OnStepXDevice, logger: Logger):
        """Initialize OnStepX rotator module.

        Args:
            device: OnStepXDevice instance (shared connection)
            logger: Python logger instance

        Raises:
            TypeError: If device is not OnStepXDevice instance
            TypeError: If logger is not Logger instance
        """
        if not isinstance(device, OnStepXDevice):
            raise TypeError('device must be OnStepXDevice instance')
        if not isinstance(logger, Logger):
            raise TypeError('logger must be Logger instance')

        self._device = device
        self._logger = logger
        self._derotator_reversed = False  # Track derotator reverse state in software

    # ====================================================================
    # STATUS AND AVAILABILITY COMMANDS
    # ====================================================================

    def is_active(self) -> bool:
        """Check if rotator is active and available.

        Queries :rA# command to determine if rotator is configured
        and operational in OnStepX controller.

        Returns:
            bool: True if rotator active, False otherwise

        Raises:
            RuntimeError: If command fails or response invalid
        """
        try:
            response = self._device.send_command(':rA#')
            return response.strip() == '1'
        except Exception as e:
            self._logger.error(f'Failed to check rotator active status: {str(e)}')
            raise RuntimeError(f'Rotator active check failed: {str(e)}')

    def get_availability(self) -> bool:
        """Check rotator availability via extended command.

        Queries :GX98# extended command to check if rotator is
        available and ready for use.

        Returns:
            bool: True if rotator available, False otherwise

        Raises:
            RuntimeError: If command fails
        """
        try:
            response = self._device.send_command(':GX98#')
            return response.strip() == '1'
        except Exception as e:
            self._logger.error(f'Failed to check rotator availability: {str(e)}')
            raise RuntimeError(f'Rotator availability check failed: {str(e)}')

    # ====================================================================
    # POSITION AND MOVEMENT STATUS COMMANDS
    # ====================================================================

    def get_position(self) -> float:
        """Get current rotator position in decimal degrees.

        Queries :rG# to get current angle. OnStepX returns sDDD*MM
        or sDDD*MM:SS format. Parses response and normalizes to 0-360 range.

        Returns:
            float: Current position in decimal degrees (0-360)

        Raises:
            RuntimeError: If command fails or response cannot be parsed
        """
        try:
            response = self._device.send_command(':rG#')
            degrees = self._dms_to_degrees(response)

            # Normalize to 0-360 range
            while degrees < 0:
                degrees += 360
            while degrees >= 360:
                degrees -= 360

            return degrees
        except Exception as e:
            self._logger.error(f'Failed to get rotator position: {str(e)}')
            raise RuntimeError(f'Get rotator position failed: {str(e)}')

    def get_is_moving(self) -> bool:
        """Check if rotator is currently moving.

        Queries :rT# status command and parses response to determine
        if rotator is in motion.

        Returns:
            bool: True if rotator is moving, False if stationary

        Raises:
            RuntimeError: If command fails
        """
        try:
            response = self._device.send_command(':rT#')
            status_dict = self._parse_status(response)
            return status_dict.get('moving', False)
        except Exception as e:
            self._logger.error(f'Failed to check rotator moving status: {str(e)}')
            raise RuntimeError(f'Get rotator moving status failed: {str(e)}')

    # ====================================================================
    # CONFIGURATION QUERY COMMANDS
    # ====================================================================

    def get_min_position(self) -> float:
        """Get minimum rotator position in degrees.

        Queries :rI# to get the lower limit of rotator travel.

        Returns:
            float: Minimum position in degrees

        Raises:
            RuntimeError: If command fails or response invalid
        """
        try:
            response = self._device.send_command(':rI#')
            min_pos = float(response.strip())
            return min_pos
        except Exception as e:
            self._logger.error(f'Failed to get rotator min position: {str(e)}')
            raise RuntimeError(f'Get min position failed: {str(e)}')

    def get_max_position(self) -> float:
        """Get maximum rotator position in degrees.

        Queries :rM# to get the upper limit of rotator travel.

        Returns:
            float: Maximum position in degrees

        Raises:
            RuntimeError: If command fails or response invalid
        """
        try:
            response = self._device.send_command(':rM#')
            max_pos = float(response.strip())
            return max_pos
        except Exception as e:
            self._logger.error(f'Failed to get rotator max position: {str(e)}')
            raise RuntimeError(f'Get max position failed: {str(e)}')

    def get_step_size(self) -> float:
        """Get rotator degrees per step.

        Queries :rD# to get the step size in degrees.

        Returns:
            float: Degrees per step

        Raises:
            RuntimeError: If command fails or response invalid
        """
        try:
            response = self._device.send_command(':rD#')
            step_size = float(response.strip())
            return step_size
        except Exception as e:
            self._logger.error(f'Failed to get rotator step size: {str(e)}')
            raise RuntimeError(f'Get step size failed: {str(e)}')

    def get_backlash(self) -> int:
        """Get rotator backlash in steps.

        Queries :rb# to get current backlash compensation value.

        Returns:
            int: Backlash in steps

        Raises:
            RuntimeError: If command fails or response invalid
        """
        try:
            response = self._device.send_command(':rb#')
            backlash = int(response.strip())
            return backlash
        except Exception as e:
            self._logger.error(f'Failed to get rotator backlash: {str(e)}')
            raise RuntimeError(f'Get backlash failed: {str(e)}')

    def get_slew_rate(self) -> float:
        """Get rotator working slew rate in degrees per second.

        Queries :rW# to get current slew rate.

        Returns:
            float: Slew rate in degrees per second

        Raises:
            RuntimeError: If command fails or response invalid
        """
        try:
            response = self._device.send_command(':rW#')
            slew_rate = float(response.strip())
            return slew_rate
        except Exception as e:
            self._logger.error(f'Failed to get rotator slew rate: {str(e)}')
            raise RuntimeError(f'Get slew rate failed: {str(e)}')

    # ====================================================================
    # CONFIGURATION SET COMMANDS
    # ====================================================================

    def set_backlash(self, steps: int) -> bool:
        """Set rotator backlash compensation.

        Sends :rb[n]# command to set backlash in steps.

        Args:
            steps: Backlash value in steps (integer)

        Returns:
            bool: True if command succeeded

        Raises:
            TypeError: If steps is not integer
            RuntimeError: If command fails
        """
        if not isinstance(steps, int):
            raise TypeError('steps must be integer')

        try:
            response = self._device.send_command(f':rb{steps}#')
            success = response.strip() == '1'
            if success:
                self._logger.debug(f'Rotator backlash set to {steps} steps')
            else:
                self._logger.warning(f'Rotator backlash set failed: {response}')
            return success
        except Exception as e:
            self._logger.error(f'Failed to set rotator backlash: {str(e)}')
            raise RuntimeError(f'Set backlash failed: {str(e)}')

    def set_move_rate(self, rate: int) -> bool:
        """Set rotator move/goto rate.

        Sends :r[n]# command to set movement rate.

        Args:
            rate: Rate setting (integer, controller-dependent)

        Returns:
            bool: True if command succeeded

        Raises:
            TypeError: If rate is not integer
            RuntimeError: If command fails
        """
        if not isinstance(rate, int):
            raise TypeError('rate must be integer')

        try:
            response = self._device.send_command(f':r{rate}#')
            success = response.strip() == '1'
            if success:
                self._logger.debug(f'Rotator move rate set to {rate}')
            else:
                self._logger.warning(f'Rotator move rate set failed: {response}')
            return success
        except Exception as e:
            self._logger.error(f'Failed to set rotator move rate: {str(e)}')
            raise RuntimeError(f'Set move rate failed: {str(e)}')

    # ====================================================================
    # ABSOLUTE AND RELATIVE MOVEMENT COMMANDS
    # ====================================================================

    def move_absolute(self, angle: float) -> bool:
        """Move rotator to absolute angle position.

        Sends :rS[sDDD*MM]# command to move to specified absolute angle.
        Converts decimal degrees to DMS format required by OnStepX.

        Args:
            angle: Target angle in decimal degrees (0-360)

        Returns:
            bool: True if command succeeded

        Raises:
            TypeError: If angle is not float/int
            ValueError: If angle is outside valid range
            RuntimeError: If command fails
        """
        if not isinstance(angle, (int, float)):
            raise TypeError('angle must be float or int')

        if not (0 <= angle <= 360):
            raise ValueError(f'Angle out of range: {angle}')

        try:
            dms_str = self._degrees_to_dms(angle)
            response = self._device.send_command(f':rS{dms_str}#')
            success = response.strip() == '1'
            if success:
                self._logger.debug(f'Rotator absolute move to {angle:.2f}° sent')
            else:
                self._logger.warning(f'Rotator absolute move failed: {response}')
            return success
        except Exception as e:
            self._logger.error(f'Failed to move rotator absolute: {str(e)}')
            raise RuntimeError(f'Move absolute failed: {str(e)}')

    def move_relative(self, offset: float) -> bool:
        """Move rotator relative to current position.

        Sends :rr[sDDD*MM]# command to move by specified offset.
        Converts decimal degrees to DMS format required by OnStepX.

        Args:
            offset: Offset in decimal degrees (positive = clockwise)

        Returns:
            bool: True if command succeeded

        Raises:
            TypeError: If offset is not float/int
            RuntimeError: If command fails
        """
        if not isinstance(offset, (int, float)):
            raise TypeError('offset must be float or int')

        try:
            dms_str = self._degrees_to_dms(offset)
            response = self._device.send_command(f':rr{dms_str}#')
            success = response.strip() == '1'
            if success:
                self._logger.debug(f'Rotator relative move by {offset:.2f}° sent')
            else:
                self._logger.warning(f'Rotator relative move failed: {response}')
            return success
        except Exception as e:
            self._logger.error(f'Failed to move rotator relative: {str(e)}')
            raise RuntimeError(f'Move relative failed: {str(e)}')

    # ====================================================================
    # CONTINUOUS MOVEMENT COMMANDS
    # ====================================================================

    def move_clockwise(self) -> None:
        """Start rotator moving clockwise.

        Sends :r># command to begin continuous clockwise motion.
        Use halt() to stop motion.

        Raises:
            RuntimeError: If command fails
        """
        try:
            self._device.send_command(':r>#')
            self._logger.debug('Rotator moving clockwise')
        except Exception as e:
            self._logger.error(f'Failed to move rotator clockwise: {str(e)}')
            raise RuntimeError(f'Move clockwise failed: {str(e)}')

    def move_counter_clockwise(self) -> None:
        """Start rotator moving counter-clockwise.

        Sends :r<# command to begin continuous counter-clockwise motion.
        Use halt() to stop motion.

        Raises:
            RuntimeError: If command fails
        """
        try:
            self._device.send_command(':r<#')
            self._logger.debug('Rotator moving counter-clockwise')
        except Exception as e:
            self._logger.error(f'Failed to move rotator counter-clockwise: {str(e)}')
            raise RuntimeError(f'Move counter-clockwise failed: {str(e)}')

    def halt(self) -> None:
        """Stop all rotator motion.

        Sends :rQ# command to halt rotator movement immediately.

        Raises:
            RuntimeError: If command fails
        """
        try:
            self._device.send_command(':rQ#')
            self._logger.debug('Rotator halted')
        except Exception as e:
            self._logger.error(f'Failed to halt rotator: {str(e)}')
            raise RuntimeError(f'Halt failed: {str(e)}')

    # ====================================================================
    # POSITION REFERENCE COMMANDS
    # ====================================================================

    def set_zero(self) -> bool:
        """Set current position as zero reference.

        Sends :rZ# command to sync rotator zero point to current position.

        Returns:
            bool: True if command succeeded

        Raises:
            RuntimeError: If command fails
        """
        try:
            response = self._device.send_command(':rZ#')
            success = response.strip() == '1'
            if success:
                self._logger.info('Rotator zero reference set')
            else:
                self._logger.warning(f'Rotator zero reference set failed: {response}')
            return success
        except Exception as e:
            self._logger.error(f'Failed to set rotator zero: {str(e)}')
            raise RuntimeError(f'Set zero failed: {str(e)}')

    def set_half_travel(self) -> bool:
        """Set current position as half-travel reference.

        Sends :rF# command to mark current position as half-travel point.

        Returns:
            bool: True if command succeeded

        Raises:
            RuntimeError: If command fails
        """
        try:
            response = self._device.send_command(':rF#')
            success = response.strip() == '1'
            if success:
                self._logger.info('Rotator half-travel reference set')
            else:
                self._logger.warning(f'Rotator half-travel set failed: {response}')
            return success
        except Exception as e:
            self._logger.error(f'Failed to set rotator half-travel: {str(e)}')
            raise RuntimeError(f'Set half-travel failed: {str(e)}')

    def move_to_half_travel(self) -> None:
        """Move rotator to half-travel position.

        Sends :rC# command to move to previously defined half-travel point.
        This is a slew command that begins motion. Use get_is_moving()
        to check completion.

        Raises:
            RuntimeError: If command fails
        """
        try:
            self._device.send_command(':rC#')
            self._logger.debug('Rotator moving to half-travel position')
        except Exception as e:
            self._logger.error(f'Failed to move to rotator half-travel: {str(e)}')
            raise RuntimeError(f'Move to half-travel failed: {str(e)}')

    # ====================================================================
    # PARK AND UNPARK COMMANDS
    # ====================================================================

    def park(self) -> bool:
        """Park rotator.

        Sends :hP# command to move rotator to park position.
        Uses same command as telescope park (controller arbitrates).

        Returns:
            bool: True if park command accepted

        Raises:
            RuntimeError: If command fails
        """
        try:
            response = self._device.send_command(':hP#')
            success = response.strip() == '1'
            if success:
                self._logger.info('Rotator park command accepted')
            else:
                self._logger.warning(f'Rotator park failed: {response}')
            return success
        except Exception as e:
            self._logger.error(f'Failed to park rotator: {str(e)}')
            raise RuntimeError(f'Park failed: {str(e)}')

    def unpark(self) -> bool:
        """Unpark rotator.

        Sends :hR# command to restore rotator to operational state
        after parking. Uses same command as telescope unpark.

        Returns:
            bool: True if unpark command succeeded

        Raises:
            RuntimeError: If command fails
        """
        try:
            response = self._device.send_command(':hR#')
            success = response.strip() == '1'
            if success:
                self._logger.info('Rotator unparked')
            else:
                self._logger.warning(f'Rotator unpark failed: {response}')
            return success
        except Exception as e:
            self._logger.error(f'Failed to unpark rotator: {str(e)}')
            raise RuntimeError(f'Unpark failed: {str(e)}')

    # ====================================================================
    # DEROTATOR COMMANDS
    # ====================================================================

    def enable_derotator(self) -> bool:
        """Enable derotator (field rotation compensation).

        Sends :r+# command to enable field rotation compensation via derotator.

        Returns:
            bool: True if command succeeded

        Raises:
            RuntimeError: If command fails
        """
        try:
            response = self._device.send_command(':r+#')
            success = response.strip() == '1'
            if success:
                self._logger.info('Derotator enabled')
            else:
                self._logger.warning(f'Derotator enable failed: {response}')
            return success
        except Exception as e:
            self._logger.error(f'Failed to enable derotator: {str(e)}')
            raise RuntimeError(f'Enable derotator failed: {str(e)}')

    def disable_derotator(self) -> bool:
        """Disable derotator (field rotation compensation).

        Sends :r-# command to disable field rotation compensation.

        Returns:
            bool: True if command succeeded

        Raises:
            RuntimeError: If command fails
        """
        try:
            response = self._device.send_command(':r-#')
            success = response.strip() == '1'
            if success:
                self._logger.info('Derotator disabled')
            else:
                self._logger.warning(f'Derotator disable failed: {response}')
            return success
        except Exception as e:
            self._logger.error(f'Failed to disable derotator: {str(e)}')
            raise RuntimeError(f'Disable derotator failed: {str(e)}')

    def reverse_derotator(self) -> bool:
        """Reverse derotator direction (toggle command).

        Sends :rR# command to reverse derotator rotation direction.
        This is a TOGGLE command - track state in software via
        _derotator_reversed flag to know current state.

        Returns:
            bool: True if command succeeded, False otherwise

        Raises:
            RuntimeError: If command fails
        """
        try:
            response = self._device.send_command(':rR#')
            success = response.strip() == '1'
            if success:
                # Toggle software state
                self._derotator_reversed = not self._derotator_reversed
                self._logger.info(f'Derotator direction reversed (now {"reversed" if self._derotator_reversed else "normal"})')
            else:
                self._logger.warning(f'Derotator reverse failed: {response}')
            return success
        except Exception as e:
            self._logger.error(f'Failed to reverse derotator: {str(e)}')
            raise RuntimeError(f'Reverse derotator failed: {str(e)}')

    def move_to_parallactic(self) -> None:
        """Move rotator to parallactic angle position.

        Sends :rP# command to rotate to position compensating for
        parallactic angle at current site and coordinates.
        This is a slew command. Use get_is_moving() to check status.

        Raises:
            RuntimeError: If command fails
        """
        try:
            self._device.send_command(':rP#')
            self._logger.debug('Rotator moving to parallactic angle')
        except Exception as e:
            self._logger.error(f'Failed to move to parallactic angle: {str(e)}')
            raise RuntimeError(f'Move to parallactic failed: {str(e)}')

    # ====================================================================
    # HELPER METHODS
    # ====================================================================

    def _degrees_to_dms(self, degrees: float) -> str:
        """Convert decimal degrees to sDDD*MM format for OnStepX.

        Converts decimal degrees to DMS (Degrees, Minutes, Seconds)
        format required by OnStepX rotator commands.

        Format: sDDD*MM (sign, 3 digit degrees, asterisk, 2 digit minutes)
        Seconds are not used for rotator commands in onstepx_device pattern.

        Args:
            degrees: Decimal degrees value

        Returns:
            str: DMS string in format sDDD*MM

        Raises:
            TypeError: If degrees is not numeric
            ValueError: If degrees is out of valid range
        """
        if not isinstance(degrees, (int, float)):
            raise TypeError('degrees must be numeric')

        # Extract sign BEFORE normalization to preserve relative move direction
        sign = '+' if degrees >= 0 else '-'
        degrees = abs(degrees)

        # Then normalize if needed (for absolute positions)
        # For relative moves, the sign is already preserved
        while degrees >= 360:
            degrees -= 360

        # Extract components
        d = int(degrees)
        remainder = (degrees - d) * 60.0
        m = int(remainder)

        # Format as sDDD*MM (no seconds for rotator)
        dms_str = f'{sign}{d:03d}*{m:02d}'
        return dms_str

    def _dms_to_degrees(self, dms_str: str) -> float:
        """Parse DMS string from OnStepX rotator response to decimal degrees.

        Handles both sDDD*MM and sDDD*MM:SS formats from :rG# response.
        Returns signed value that may be negative or exceed 360.
        Caller should normalize to 0-360 range if needed.

        Args:
            dms_str: DMS string in format sDDD*MM or sDDD*MM:SS

        Returns:
            float: Decimal degrees (may be negative or > 360)

        Raises:
            ValueError: If format cannot be parsed
        """
        dms_str = dms_str.strip()
        if not dms_str:
            raise ValueError('Empty DMS string')

        # Extract sign
        sign = 1.0
        if dms_str[0] == '-':
            sign = -1.0
            dms_str = dms_str[1:]
        elif dms_str[0] == '+':
            dms_str = dms_str[1:]

        # Replace separators with spaces for split
        dms_str = dms_str.replace('*', ' ').replace(':', ' ').replace("'", ' ')

        parts = dms_str.split()
        if len(parts) < 1:
            raise ValueError(f'Invalid DMS format')

        try:
            degrees = float(parts[0])
            minutes = float(parts[1]) if len(parts) > 1 else 0.0
            seconds = float(parts[2]) if len(parts) > 2 else 0.0
        except (ValueError, IndexError) as e:
            raise ValueError(f'Invalid DMS format: {str(e)}')

        total_degrees = sign * (degrees + minutes / 60.0 + seconds / 3600.0)
        return total_degrees

    def _parse_status(self, status_str: str) -> dict:
        """Parse :rT# status response into dictionary.

        Analyzes rotator status string to extract motion state and
        other status information.

        Status format varies by OnStepX version. This implementation
        checks for common indicators of motion (e.g., "moving" substring,
        non-zero motion flags, or status bytes).

        Args:
            status_str: Status string from :rT# command

        Returns:
            dict: Status dictionary with 'moving' key (bool) and
                  other status fields if applicable

        Raises:
            ValueError: If status string cannot be parsed
        """
        status_dict = {'moving': False}

        if not status_str:
            return status_dict

        status_str = status_str.strip().lower()

        # Check for common motion indicators
        if 'moving' in status_str or 'slewing' in status_str:
            status_dict['moving'] = True

        # Check for motion flag characters/bytes
        # OnStepX may use special characters to indicate motion
        if any(char in status_str for char in ['*', '!', '>', '<']):
            status_dict['moving'] = True

        # Check for numeric status codes that indicate motion
        # (implementation depends on OnStepX version)
        try:
            # Try to parse first character as hex/decimal status
            first_char = status_str[0]
            if first_char.isdigit():
                status_code = int(first_char)
                # Status code 1-3 typically indicate motion in OnStepX
                if status_code > 0:
                    status_dict['moving'] = True
        except (ValueError, IndexError):
            pass

        return status_dict
