import math
import requests

ESP32_IP = "192.168.45.206"


class ESP32Client:
    def __init__(self, ip: str = ESP32_IP):
        self.base_url = f"http://{ip}"

    def set_action(self, action: float):
        # action: -1.0 ~ 1.0
        if not math.isfinite(action) or not -1.0 <= action <= 1.0:
            raise ValueError("action must be between -1 and 1")

        pwm = round(abs(action) * 255)
        direction = 1 if action >= 0 else -1
        self.set_motor(pwm, direction)

    def set_motor(self, pwm: int, direction: int):
        """Send an already computed PWM without applying another action mapping."""
        if type(pwm) is not int or not 0 <= pwm <= 255 or direction not in (-1, 1):
            raise ValueError("Expected integer PWM 0..255 and direction -1 or 1")
        response = requests.get(
            f"{self.base_url}/motor",
            params={
                "speed": pwm,
                "dir": direction
            },
            timeout=1
        )
        response.raise_for_status()

    def stop(self):
        response = requests.get(
            f"{self.base_url}/stop",
            timeout=1
        )
        response.raise_for_status()
