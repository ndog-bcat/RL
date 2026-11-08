"""Single-owner hardware loop. Call update regularly, including between RL actions."""

from time import monotonic

from requests import RequestException

from .esp32_client import ESP32Client
from .motor_controller import MotorCommand, MotorController, MotorState


class ESP32Adapter:
    def __init__(self, controller: MotorController, client: ESP32Client, clock=monotonic):
        self.controller = controller
        self.client = client
        self._clock = clock
        self._last_command = None
        self._sent_at = 0.0

    def update(self) -> MotorCommand:
        """Advance the FSM and synchronously deliver changes or a due heartbeat."""
        now = self._clock()
        previous = self._last_command
        command = self.controller.update(now)
        try:
            if previous and previous.pwm and now - self._sent_at >= 1.5:
                raise TimeoutError("Missed ESP32 motor watchdog deadline")
            if command == previous and (not command.pwm or now - self._sent_at < 0.3):
                return command
            if command.pwm:
                self.client.set_motor(command.pwm, command.direction)
                if previous is None or not previous.pwm:
                    self.controller.confirm_start(self._clock())
            else:
                self.client.stop()
                self.controller.confirm_stop(self._clock())
        except (RequestException, TimeoutError):
            self.controller.set_error()
            self._last_command = MotorCommand(0, 0)
            try:
                self.client.stop()
            except RequestException:
                pass  # Preserve the original failure. Physical stop is unconfirmed.
            raise
        self._last_command = command
        self._sent_at = now
        return command
