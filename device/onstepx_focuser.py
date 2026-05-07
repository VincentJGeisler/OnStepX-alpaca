# -*- coding: utf-8 -*-
# =================================================================
# onstepx_focuser.py - OnStepX Focuser Communication Module
# =================================================================
#
# Implements high-level focuser commands for OnStepX controller.
# Supports 6 independent focuser units with temperature compensation,
# backlash correction, and motor power control.
#
# Command Reference: OnStepX COMMANDS.md lines 828-949
#
# Author: Vince Geisler
# Python Compatibility: Requires Python 3.7 or later
#
# =================================================================

from logging import Logger
from typing import Optional
from exceptions import DriverException

try:
    from .onstepx_device import OnStepXDevice
except ImportError:
    from onstepx_device import OnStepXDevice


class OnStepXFocuser:
    """High-level OnStepX focuser controller supporting up to 6 independent units.

    Manages all focuser operations including:
    - Position control (absolute/relative movement, homing)
    - Temperature compensation with configurable coefficients
    - Motor power management
    - Status monitoring (position, moving state, temperature)
    - Backlash compensation

    Each focuser instance represents a single focuser unit (1-6) connected
    to an OnStepX controller. The instance shares a single serial/TCP connection
    via an OnStepXDevice instance and uses the :FA[n]# command to select the
    correct focuser before each operation.

    Thread Safety:
    All communication is thread-safe via the shared OnStepXDevice._lock.
    Each public method sends :FA[n]# to select the focuser, ensuring correct
    unit selection in multi-threaded environments.

    Attributes:
        _device: Shared OnStepXDevice instance
        _logger: Python logger instance
        _focuser_number: Focuser unit number (1-6)
    """

    def __init__(
        self,
        device: OnStepXDevice,
        logger: Logger,
        focuser_number: int = 1
    ):
        """Initialize OnStepX focuser controller.

        Args:
            device: Shared OnStepXDevice instance for command communication
            logger: Python logger instance for debug/error logging
            focuser_number: Focuser unit number (1-6). Defaults to 1 (primary).

        Raises:
            ValueError: If focuser_number is not in range 1-6
        """
        if not 1 <= focuser_number <= 6:
            raise ValueError(f'Focuser number must be 1-6, got {focuser_number}')

        self._device = device
        self._logger = logger
        self._focuser_number = focuser_number

    def _ensure_focuser_selected(self) -> None:
        """Ensure correct focuser is selected via :FA[n]# command.

        This MUST be called at the start of every public method to guarantee
        the correct focuser unit receives subsequent commands. In multi-focuser
        setups, selection is NOT persistent across commands.

        Sends: :FA[n]# where n is the focuser number (1-6)
        Returns: "1" on success

        Raises:
            DriverException: If focuser selection fails
        """
        response = self._device.send_command(f':FA{self._focuser_number}#')
        if response != '1':
            raise DriverException(
                0x408,
                f'Failed to select focuser {self._focuser_number}: {response}'
            )

    def is_active(self) -> bool:
        """Check if focuser is active and available.

        Issues: :FA#
        Returns: 1 if active, 0 if not available/disabled

        Returns:
            bool: True if focuser is active, False otherwise

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':FA#')
        try:
            return response == '1'
        except Exception as e:
            raise DriverException(0x500, f'Failed to check focuser active status: {str(e)}')

    def get_position(self) -> int:
        """Get current focuser position.

        Issues: :FG# (GET mode - not after :FS#)
        Returns: Current position in microns or steps (depending on focuser mode)

        CRITICAL: This command has dual meaning in OnStepX:
        - Standalone :FG# = GET current position
        - After :FS[n]# = GOTO target position
        This method ONLY retrieves current position. For absolute moves, use move_absolute().

        Returns:
            int: Current position in microns or steps

        Raises:
            DriverException: If command fails or response is invalid
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':FG#')
        try:
            position = int(response)
            return position
        except ValueError:
            raise DriverException(0x500, f'Invalid position response: {response}')

    def get_is_moving(self) -> bool:
        """Check if focuser is currently moving.

        Issues: :FT# (status command)
        Returns: Status code (0=stopped, 1=moving, other values = error states)

        Returns:
            bool: True if focuser is moving, False if stopped

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':FT#')
        try:
            status = int(response)
            return status == 1
        except ValueError:
            raise DriverException(0x500, f'Invalid status response: {response}')

    def get_mode(self) -> int:
        """Get focuser mode code.

        Issues: :Fp#
        Returns: Mode code (0=microns, 1=steps, other = undefined)

        Returns:
            int: Focuser mode code

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':Fp#')
        try:
            mode = int(response)
            return mode
        except ValueError:
            raise DriverException(0x500, f'Invalid mode response: {response}')

    def get_full_in_position(self) -> int:
        """Get full-in (home) position.

        Issues: :FI#
        Returns: Position in microns or steps

        Returns:
            int: Full-in position

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':FI#')
        try:
            position = int(response)
            return position
        except ValueError:
            raise DriverException(0x500, f'Invalid full-in position response: {response}')

    def get_max_position(self) -> int:
        """Get maximum (full-out) position.

        Issues: :FM#
        Returns: Position in microns or steps

        Returns:
            int: Maximum position

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':FM#')
        try:
            position = int(response)
            return position
        except ValueError:
            raise DriverException(0x500, f'Invalid max position response: {response}')

    def get_temperature(self) -> float:
        """Get focuser temperature from sensor.

        Issues: :Ft#
        Returns: Temperature in degrees Celsius (n.n format)

        Returns:
            float: Temperature in degrees Celsius

        Raises:
            DriverException: If temperature sensor not available or command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':Ft#')
        try:
            temp = float(response)
            return temp
        except ValueError:
            raise DriverException(0x500, 'Temperature sensor not available')

    def get_temp_differential(self) -> float:
        """Get temperature differential from reference.

        Issues: :Fe#
        Returns: Differential in degrees Celsius (n.n format)

        Returns:
            float: Temperature differential in degrees Celsius

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':Fe#')
        try:
            diff = float(response)
            return diff
        except ValueError:
            raise DriverException(0x500, f'Invalid temperature differential response: {response}')

    def get_microns_per_step(self) -> float:
        """Get microns per step conversion factor.

        Issues: :Fu#
        Returns: Conversion factor (n.n format)

        Returns:
            float: Microns per step

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':Fu#')
        try:
            factor = float(response)
            return factor
        except ValueError:
            raise DriverException(0x500, f'Invalid microns per step response: {response}')

    def get_backlash(self) -> int:
        """Get backlash compensation value.

        Issues: :FB#
        Returns: Backlash in steps or microns

        Returns:
            int: Backlash value

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':FB#')
        try:
            backlash = int(response)
            return backlash
        except ValueError:
            raise DriverException(0x500, f'Invalid backlash response: {response}')

    def set_backlash(self, value: int) -> None:
        """Set backlash compensation value.

        Issues: :FB[n]# where n is the backlash value in steps or microns
        Returns: "1" on success

        Args:
            value: Backlash value in steps or microns (0-1000 typical)

        Raises:
            DriverException: If command fails or value is invalid
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(f':FB{value}#')
        if response != '1':
            raise DriverException(0x408, f'Failed to set backlash to {value}: {response}')

    def get_temp_comp_coefficient(self) -> float:
        """Get temperature compensation coefficient.

        Issues: :FC#
        Returns: Coefficient in microns per °C (sn.n format, where s is sign)

        Returns:
            float: Coefficient in microns per °C

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':FC#')
        try:
            coeff = float(response)
            return coeff
        except ValueError:
            raise DriverException(0x500, f'Invalid temperature coefficient response: {response}')

    def set_temp_comp_coefficient(self, value: float) -> None:
        """Set temperature compensation coefficient.

        Issues: :FC[sn.n]# where s is optional sign, n.n is the coefficient
        Returns: "1" on success

        Args:
            value: Coefficient in microns per °C. Positive = move out as temperature falls

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(f':FC{value}#')
        if response != '1':
            raise DriverException(
                0x408,
                f'Failed to set temperature coefficient to {value}: {response}'
            )

    def get_temp_comp_enabled(self) -> bool:
        """Get temperature compensation enabled status.

        Issues: :Fc#
        Returns: "1" if enabled, "0" if disabled

        Returns:
            bool: True if temperature compensation is enabled, False otherwise

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':Fc#')
        try:
            return response == '1'
        except Exception as e:
            raise DriverException(0x500, f'Failed to check temp comp status: {str(e)}')

    def set_temp_comp_enabled(self, enabled: bool) -> None:
        """Enable or disable temperature compensation.

        Issues: :Fc[n]# where n=0 (disabled) or n=1 (enabled)
        Returns: "1" on success

        Args:
            enabled: True to enable, False to disable

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        value = '1' if enabled else '0'
        response = self._device.send_command(f':Fc{value}#')
        if response != '1':
            status = 'enable' if enabled else 'disable'
            raise DriverException(0x408, f'Failed to {status} temp comp: {response}')

    def get_temp_comp_deadband(self) -> int:
        """Get temperature compensation deadband.

        Issues: :FD#
        Returns: Deadband in steps or microns

        Returns:
            int: Deadband value

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':FD#')
        try:
            deadband = int(response)
            return deadband
        except ValueError:
            raise DriverException(0x500, f'Invalid deadband response: {response}')

    def set_temp_comp_deadband(self, value: int) -> None:
        """Set temperature compensation deadband.

        Issues: :FD[n]# where n is the deadband in steps or microns
        Returns: "1" on success

        Args:
            value: Deadband in steps or microns (prevents temperature hunting)

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(f':FD{value}#')
        if response != '1':
            raise DriverException(0x408, f'Failed to set deadband to {value}: {response}')

    def get_motor_power(self) -> int:
        """Get DC motor power level.

        Issues: :FP#
        Returns: Power level as percentage (0-100)

        Returns:
            int: Motor power as percentage (0-100)

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':FP#')
        try:
            power = int(response)
            return power
        except ValueError:
            raise DriverException(0x500, f'Invalid motor power response: {response}')

    def set_motor_power(self, percent: int) -> None:
        """Set DC motor power level.

        Issues: :FP[n]# where n is the power percentage (0-100)
        Returns: "1" on success

        Args:
            percent: Motor power percentage (0-100)

        Raises:
            DriverException: If command fails or percent is out of range
        """
        if not 0 <= percent <= 100:
            raise DriverException(0x400, f'Motor power must be 0-100, got {percent}')

        self._ensure_focuser_selected()
        response = self._device.send_command(f':FP{percent}#')
        if response != '1':
            raise DriverException(0x408, f'Failed to set motor power to {percent}%: {response}')

    def halt(self) -> None:
        """Stop all focuser movement immediately.

        Issues: :FQ#
        Returns: No response

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        try:
            self._device.send_command(':FQ#')
        except Exception as e:
            raise DriverException(0x408, f'Failed to halt focuser: {str(e)}')

    def move_in(self) -> None:
        """Start continuous movement toward telescope (full-in direction).

        Issues: :F+#
        Returns: No response

        Movement continues until halt() is called or hardware limit reached.

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        try:
            self._device.send_command(':F+#')
        except Exception as e:
            raise DriverException(0x408, f'Failed to move focuser in: {str(e)}')

    def move_out(self) -> None:
        """Start continuous movement away from telescope (full-out direction).

        Issues: :F-#
        Returns: No response

        Movement continues until halt() is called or hardware limit reached.

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        try:
            self._device.send_command(':F-#')
        except Exception as e:
            raise DriverException(0x408, f'Failed to move focuser out: {str(e)}')

    def move_full_in(self) -> None:
        """Move to full-in (home) position.

        Issues: :FF#
        Returns: No response

        This is an absolute move to the configured full-in position.
        The focuser will move continuously until reaching the home position.

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        try:
            self._device.send_command(':FF#')
        except Exception as e:
            raise DriverException(0x408, f'Failed to move focuser to full-in: {str(e)}')

    def move_absolute(self, position: int) -> None:
        """Move to absolute position.

        Issues: :FS[n]# immediately followed by :FG#

        CRITICAL: This method uses OnStepX's dual-purpose :FG# command:
        - First send :FS[n]# to set the target position
        - Then send :FG# which, in this context, means GOTO (not GET)
        - The focuser will move continuously to the target

        Args:
            position: Target position in microns or steps

        Raises:
            DriverException: If either command fails
        """
        self._ensure_focuser_selected()
        try:
            response = self._device.send_command(f':FS{position}#')
            if response != '1':
                raise DriverException(
                    0x408,
                    f'Failed to set target position to {position}: {response}'
                )
            self._device.send_command(':FG#')
        except DriverException:
            raise
        except Exception as e:
            raise DriverException(0x408, f'Failed to move to position {position}: {str(e)}')

    def set_zero(self) -> None:
        """Set current position as zero reference point.

        Issues: :FZ#
        Returns: "1" on success

        This command sets the current focuser position as the zero/home reference.
        Useful for calibration or re-centering after hardware maintenance.

        Raises:
            DriverException: If command fails
        """
        self._ensure_focuser_selected()
        response = self._device.send_command(':FZ#')
        if response != '1':
            raise DriverException(0x408, f'Failed to set current position as zero: {response}')
