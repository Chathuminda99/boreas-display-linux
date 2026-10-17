"""GAMDIAS BOREAS digital display HID protocol.

Matches the reports sent by the official Windows app.

Every transfer is one 64-byte HID report with no report ID. On hidraw the
report is written as 65 bytes with a leading 0x00 report-ID byte, which is
also how the Windows app lays out its buffer (index 0 = report ID).

    [0]  0x00  report ID (unnumbered)
    [1]  0x3A  header 1
    [2]  0xB5  header 2
    [3]  cmd   0xFF = query device info, 0x01 = update display
    [4]  d0    hundreds / thousands digit (0-9, 0x20 = blank)
    [5]  d1
    [6]  d2
    [7]  d3    last digit (tenths for temperature)
    [8]  dot   1 = show decimal point
    [9]  unit  1 = Celsius, 0 = Fahrenheit
    [10] cpu   1 = CPU icon (temperature mode)
    [11] mode  0 = CPU temperature, 1 = fan RPM
    [12] flash 1 = blink display (over-temperature alarm)
    [13] sum   (sum of bytes [0..12]) & 0xFF
    [14..64]   zero

The info reply (64 bytes, as read from hidraw without a report-ID byte):
    [3] firmware major, [4] firmware minor, [5] default unit (1 = C),
    [6] CPU mode supported, [7] fan mode supported.
"""

from dataclasses import dataclass

REPORT_LEN = 65  # report ID byte + 64 data bytes
HEADER = (0x3A, 0xB5)
CMD_INFO = 0xFF
CMD_DISPLAY = 0x01
BLANK = 0x20

MODE_TEMP = 0
MODE_FAN = 1

# USB IDs: 0xB53A (GAMDIAS) and 0xB554 (OEM variant).
VENDOR_ID = 0x1B80
PRODUCT_IDS = {0xB53A: "BOREAS Digital Display", 0xB554: "BOREAS Digital Display (OEM)"}


def checksum(buf):
    return sum(buf[:13]) & 0xFF


def _packet(cmd, digits, dot, unit, cpu, mode, flash):
    buf = bytearray(REPORT_LEN)
    buf[1], buf[2] = HEADER
    buf[3] = cmd
    buf[4:8] = bytes(digits)
    buf[8] = dot
    buf[9] = unit
    buf[10] = cpu
    buf[11] = mode
    buf[12] = flash
    buf[13] = checksum(buf)
    return bytes(buf)


def info_request():
    return _packet(CMD_INFO, (BLANK,) * 4, 0, 1, 1, 0, 0)


def temp_digits(celsius, fahrenheit=False):
    """Four digits for 'XXX.X' with a blank leading digit when it is zero."""
    value = celsius * 1.8 + 32 if fahrenheit else celsius
    tenths = max(0, min(9999, int(round(value * 10))))
    d = [tenths // 1000, tenths // 100 % 10, tenths // 10 % 10, tenths % 10]
    if d[0] == 0:
        d[0] = BLANK
    return d


def rpm_digits(rpm):
    rpm = max(0, min(9999, int(round(rpm))))
    d = [rpm // 1000, rpm // 100 % 10, rpm // 10 % 10, rpm % 10]
    if d[0] == 0:
        d[0] = BLANK
    return d


def temp_packet(celsius, fahrenheit=False, flash=False):
    return _packet(CMD_DISPLAY, temp_digits(celsius, fahrenheit), 1,
                   0 if fahrenheit else 1, 1, MODE_TEMP, int(flash))


def fan_packet(rpm, flash=False):
    return _packet(CMD_DISPLAY, rpm_digits(rpm), 0, 0, 0, MODE_FAN, int(flash))


def raw_packet(digits, dot=False, fahrenheit=False, mode=MODE_TEMP, flash=False):
    """Arbitrary digits, for testing segments. Each digit 0-9 or None for blank."""
    d = [BLANK if x is None else int(x) for x in digits]
    if len(d) != 4 or any(x != BLANK and not 0 <= x <= 9 for x in d):
        raise ValueError("need exactly 4 digits (0-9 or blank)")
    cpu = 1 if mode == MODE_TEMP else 0
    return _packet(CMD_DISPLAY, d, int(dot), 0 if fahrenheit else 1, cpu, mode, int(flash))


def without_flash(packet):
    """Same frame with blinking turned off."""
    buf = bytearray(packet)
    buf[12] = 0
    buf[13] = checksum(buf)
    return bytes(buf)



@dataclass
class DeviceInfo:
    fw_major: int
    fw_minor: int
    default_celsius: bool
    supports_cpu: bool
    supports_fan: bool

    @property
    def firmware(self):
        return f"{self.fw_major}.{self.fw_minor}"


def parse_info(reply):
    """Parse a 64-byte info reply (hidraw read, no report-ID byte)."""
    if len(reply) < 8:
        raise ValueError(f"short info reply ({len(reply)} bytes)")
    return DeviceInfo(reply[3], reply[4], reply[5] == 1, reply[6] == 1, reply[7] == 1)
