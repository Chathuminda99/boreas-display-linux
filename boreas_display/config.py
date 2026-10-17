"""Settings shared by the daemon, CLI and GUI.

Mirrors the options of the Windows app: mode, unit, and the over-temperature alarm.
"""

import configparser
import os
from dataclasses import dataclass, fields
from pathlib import Path

SECTION = "boreas"


def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base, "boreas-display", "config.ini")


@dataclass
class Settings:
    mode: str = "temp"          # "temp" (CPU temperature) or "fan" (fan RPM)
    unit: str = "c"             # "c" or "f"
    alarm: bool = False         # flash the display when temperature >= threshold
    alarm_threshold: int = 90   # in the selected unit, like the Windows app
    interval: float = 0.5       # seconds between updates (Windows uses 0.25)
    temp_sensor: str = ""       # "<chip>/<label>"; empty = auto-detect
    fan_sensor: str = ""        # "<chip>/<label>"; empty = auto-detect
    device: str = ""            # /dev/hidrawN; empty = auto-detect

    def validate(self):
        if self.mode not in ("temp", "fan"):
            raise ValueError("mode must be 'temp' or 'fan'")
        if self.unit not in ("c", "f"):
            raise ValueError("unit must be 'c' or 'f'")
        if not 0.1 <= self.interval <= 10:
            raise ValueError("interval must be between 0.1 and 10 seconds")
        return self


def load(path=None):
    path = path or config_path()
    s = Settings()
    cp = configparser.ConfigParser()
    cp.read(path)
    if cp.has_section(SECTION):
        sec = cp[SECTION]
        for f in fields(Settings):
            if f.name not in sec:
                continue
            try:
                if f.type is bool or f.type == "bool":
                    value = sec.getboolean(f.name)
                elif f.type is int or f.type == "int":
                    value = sec.getint(f.name)
                elif f.type is float or f.type == "float":
                    value = sec.getfloat(f.name)
                else:
                    value = sec.get(f.name).strip()
            except ValueError:
                continue
            setattr(s, f.name, value)
    try:
        return s.validate()
    except ValueError:
        return Settings()


def save(settings, path=None):
    path = path or config_path()
    settings.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    cp = configparser.ConfigParser()
    cp[SECTION] = {f.name: str(getattr(settings, f.name)).lower()
                   if isinstance(getattr(settings, f.name), bool)
                   else str(getattr(settings, f.name)) for f in fields(Settings)}
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as fh:
        cp.write(fh)
    os.replace(tmp, path)
