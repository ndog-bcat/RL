"""모터 실험 규격에 따른 비차단 PWM 제어기 (docs/motor_control.md)."""

from dataclasses import dataclass
from enum import Enum, auto
from math import isfinite


@dataclass(frozen=True)
class MotorConfig:
    start_pwm: int = 90
    min_pwm: int = 60
    max_pwm: int = 180
    start_duration: float = 1.0
    reverse_delay: float = 0.5

    def __post_init__(self):
        if not all(type(v) is int for v in (self.min_pwm, self.start_pwm, self.max_pwm)):
            raise ValueError("PWM settings must be integers")
        if not 0 < self.min_pwm <= self.start_pwm <= self.max_pwm <= 255:
            raise ValueError("Expected 0 < min_pwm <= start_pwm <= max_pwm <= 255")
        for duration in (self.start_duration, self.reverse_delay):
            if not isfinite(duration) or duration < 0:
                raise ValueError("Durations must be finite and nonnegative")


class MotorState(Enum):
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    REVERSING = auto()
    ERROR = auto()


@dataclass(frozen=True)
class MotorCommand:
    pwm: int
    direction: int


_STOP = MotorCommand(0, 0)


class MotorController:
    def __init__(self, config: MotorConfig = MotorConfig()):
        self.config = config
        self.state = MotorState.STOPPED
        self._target = _STOP
        self._last_direction = 0
        self._driving = False
        self._restart_after = 0.0
        self._running_after = 0.0

    def set_action(self, action: float) -> None:
        if not -1 <= action <= 1:
            raise ValueError("Action must be in [-1, 1]")
        if self.state is MotorState.ERROR:
            return
        if action == 0:
            self.stop()
            return
        span = self.config.max_pwm - self.config.min_pwm
        pwm = round(self.config.min_pwm + span * abs(action))
        self._target = MotorCommand(pwm, 1 if action > 0 else -1)

    def update(self, current_time: float) -> MotorCommand:
        """Use monotonic seconds. In simulation commands take effect at this tick."""
        if not isfinite(current_time):
            raise ValueError("Expected a finite monotonic time")
        direction = self._target.direction
        opposite = direction != self._last_direction

        # Even if a new action arrived immediately after stop(), emit coast first.
        if self._driving and (self.state is MotorState.STOPPED or opposite):
            self._driving = False
            self._restart_after = current_time + self.config.reverse_delay
            if direction:
                self.state = MotorState.REVERSING
            return _STOP
        if not direction:
            return _STOP

        if not self._driving:
            if self._last_direction and (opposite or self.state is MotorState.REVERSING):
                if current_time < self._restart_after:
                    self.state = MotorState.REVERSING
                    return _STOP
            self.state = MotorState.STARTING
            self._driving = True
            self._last_direction = direction
            self._running_after = current_time + self.config.start_duration
            return MotorCommand(self.config.start_pwm, direction)

        if current_time < self._running_after:
            return MotorCommand(self.config.start_pwm, direction)
        self.state = MotorState.RUNNING
        return self._target

    def confirm_start(self, current_time: float) -> None:
        """Anchor the startup hold to the first successful hardware start ACK."""
        if self.state is MotorState.STARTING:
            self._running_after = current_time + self.config.start_duration

    def confirm_stop(self, current_time: float) -> None:
        """Hardware adapter calls once on the first coast ACK before the next update."""
        if not isfinite(current_time):
            raise ValueError("Expected a finite monotonic time")
        if not self._driving:
            self._restart_after = max(self._restart_after, current_time + self.config.reverse_delay)

    def stop(self) -> None:
        self._target = _STOP
        if self.state is not MotorState.ERROR:
            self.state = MotorState.STOPPED

    def set_error(self) -> None:
        """Latch the fault. Create a new controller after explicit recovery."""
        self.stop()
        self.state = MotorState.ERROR
