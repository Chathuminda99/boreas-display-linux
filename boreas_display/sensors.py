"""CPU temperature and fan speed from Linux hwmon (replaces CPUID SDK on Windows)."""

from dataclasses import dataclass
from pathlib import Path

HWMON = Path("/sys/class/hwmon")

# (driver name, preferred labels in order). Empty label list = any temp input.
CPU_TEMP_PREFERENCE = [
    ("coretemp", ["Package id 0"]),
    ("k10temp", ["Tctl", "Tdie"]),
    ("zenpower", ["Tdie", "Tctl"]),
    ("cpu_thermal", []),
    ("acpitz", []),
]


@dataclass
class Sensor:
    path: Path      # .../tempN_input or .../fanN_input
    chip: str
    label: str

    @property
    def id(self):
        """Stable identifier '<chip>/<label>' used in the config."""
        return f"{self.chip}/{self.label}"

    def read(self):
        """Value in degrees C (temp) or RPM (fan); None if unreadable."""
        try:
            raw = int(self.path.read_text().strip())
        except (OSError, ValueError):
            return None
        return raw / 1000.0 if self.path.name.startswith("temp") else float(raw)


def _sensors(kind):
    out = []
    if not HWMON.is_dir():
        return out
    for chip_dir in sorted(HWMON.iterdir(), key=lambda p: p.name):
        try:
            chip = (chip_dir / "name").read_text().strip()
        except OSError:
            continue
        inputs = sorted(chip_dir.glob(f"{kind}*_input"),
                        key=lambda p: int(p.name[len(kind):-6] or 0))
        for inp in inputs:
            label_file = inp.with_name(inp.name.replace("_input", "_label"))
            try:
                label = label_file.read_text().strip()
            except OSError:
                label = inp.name[:-6]
            out.append(Sensor(inp, chip, label))
    return out


def temp_sensors():
    return _sensors("temp")


def fan_sensors():
    return _sensors("fan")


def _by_id(sensors, sensor_id):
    for s in sensors:
        if s.id == sensor_id or str(s.path) == sensor_id:
            return s
    return None


def find_cpu_temp(sensor_id=""):
    temps = temp_sensors()
    if sensor_id:
        return _by_id(temps, sensor_id)
    for chip, labels in CPU_TEMP_PREFERENCE:
        candidates = [s for s in temps if s.chip == chip]
        for label in labels:
            for s in candidates:
                if s.label == label:
                    return s
        if candidates and not labels:
            return candidates[0]
    return None


def find_fan(sensor_id=""):
    """The Windows app picks the fan whose name starts with 'CPU'; mirror that,
    falling back to the first fan that is spinning."""
    fans = fan_sensors()
    if sensor_id:
        return _by_id(fans, sensor_id)
    for s in fans:
        if s.label.lower().startswith("cpu"):
            return s
    for s in fans:
        if (s.read() or 0) > 0:
            return s
    return fans[0] if fans else None
