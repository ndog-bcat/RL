
from pathlib import Path
import json

Import("env")

root = Path(env.subst("$PROJECT_DIR"))
env_path = root / ".env"

if not env_path.exists():
    raise RuntimeError("HW/.env file not found")

config = {}

for line in env_path.read_text(encoding="utf-8-sig").splitlines():
    line = line.strip()

    if not line or line.startswith("#"):
        continue

    key, sep, value = line.partition("=")

    if sep:
        config[key.strip()] = value.strip().strip("\"'")

for key in ("WIFI_SSID", "WIFI_PASSWORD"):
    if not config.get(key):
        raise RuntimeError(f"Missing {key} in .env")

header = (
    "#pragma once\n"
    f'#define WIFI_SSID {json.dumps(config["WIFI_SSID"], ensure_ascii=False)}\n'
    f'#define WIFI_PASSWORD {json.dumps(config["WIFI_PASSWORD"], ensure_ascii=False)}\n'
)

output = root / "include" / "wifi_secrets.h"
output.parent.mkdir(exist_ok=True)
output.write_text(header, encoding="utf-8")
