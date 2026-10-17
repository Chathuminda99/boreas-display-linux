# boreas-display-linux: GAMDIAS BOREAS digital display on Linux (ZEUS CAST alternative)

**Looking for GAMDIAS ZEUS CAST for Linux?** GAMDIAS releases ZEUS CAST only for
Windows. This project is an unofficial, open-source Linux alternative for the
**GAMDIAS BOREAS Digital Display** CPU cooler (USB `1b80:b53a`, and the OEM variant `1b80:b554`).

It shows the CPU temperature (or fan RPM) on the cooler's 4-digit display, in °C or °F.
Like ZEUS CAST, it can make the display blink when the temperature passes a threshold.
It runs as a small background service and comes with a command-line tool and a GTK 4 settings window.

It needs only Python 3.8+ from the standard library. The settings window needs GTK 4 and PyGObject.
It works on any distribution with systemd: Fedora, Ubuntu, Debian, Arch, openSUSE and others.

## Install

```bash
git clone https://github.com/Chathuminda99/boreas-display-linux.git
cd boreas-display-linux
./install.sh            # per-user install; asks for sudo once for the udev rule
boreas-display gui      # or open "BOREAS Display" from the app menu
```

`install.sh` does the following:
- copies the app to `~/.local/share/boreas-display` and the launcher to `~/.local/bin/boreas-display`;
- installs `/etc/udev/rules.d/70-gamdias-boreas.rules`, which makes the HID device readable and writable by local users (mode 0666). This also covers remote desktop sessions and the user service;
- enables the `boreas-display.service` **systemd user service**, which keeps the display updated in the background.

If an older version of this project is installed under the name `zeus-cast`, the installer removes it and keeps your settings.

To remove it, run `./install.sh --uninstall`.

## Usage

```
boreas-display list                         # connected displays
boreas-display info                         # firmware + supported modes
boreas-display sensors                      # hwmon sensors (* = the one in use)
boreas-display config --unit f              # °C / °F
boreas-display config --mode fan            # fan RPM instead of CPU temp
boreas-display config --alarm on --threshold 85
boreas-display config --temp-sensor "k10temp/Tctl"
boreas-display run -v                       # run the daemon in the foreground
boreas-display show --temp 42.5 --hold      # fixed value for testing (stop the service first)
boreas-display show --digits 8888 --dot     # segment test
```

Settings are stored in `~/.config/boreas-display/config.ini`. The daemon reloads the file automatically when it changes.

**Sensors.** CPU temperature comes from hwmon: `coretemp` on Intel, `k10temp`/`zenpower` on AMD. Fan mode needs a hwmon fan input, which usually means loading a Super-I/O driver such as `nct6775` or `it87`. The Windows app picks the fan whose name starts with "CPU", and this tool does the same. Your unit's firmware reports whether it supports fan mode; check with `boreas-display info`.

## FAQ

**Is there a Linux version of GAMDIAS ZEUS CAST?**
No, ZEUS CAST is Windows-only. For the BOREAS digital display, this project covers
what ZEUS CAST does: temperature or fan RPM, °C/°F, and the over-temperature alarm.

**The display on my BOREAS cooler is blank or frozen on Linux. Why?**
The display shows nothing until software sends it values. Without ZEUS CAST running, nothing
does. Install this project and the background service keeps it updated.

**Can the display show text?**
No. The firmware only draws the digits 0–9 and a blank. Other values show as a dash or a blank.

**Does it support other GAMDIAS devices?**
No, see [Scope](#scope).

## Protocol

The display takes one 64-byte HID report, with no report ID:

| byte | value |
|-----:|-------|
| 0 | `0x00` report ID (hidraw write prefix) |
| 1–2 | `3A B5` header |
| 3 | `FF` = query info, `01` = update display |
| 4–7 | 4 digits, 0–9, `0x20` = blank. Temperature is `XXX.X`. The firmware has no letter font: other values show as a dash or a blank. |
| 8 | decimal point (1 in temperature mode) |
| 9 | unit: 1 = °C, 0 = °F |
| 10 | CPU icon (1 in temperature mode) |
| 11 | mode: 0 = CPU temperature, 1 = fan RPM |
| 12 | blink (alarm) |
| 13 | checksum = sum(bytes 0..12) & 0xFF |

The device acknowledges every report. The reply to `FF` gives the firmware
major/minor version, the default unit, and the CPU/fan capability flags.
`tests/test_protocol.py` checks the packets against the ones the Windows app sends
and against a reply captured from a real unit.

One deliberate difference: the Windows app computes the tenths digit separately
from the other digits, so a value like 45.97 °C can produce an invalid digit 10.
This tool rounds once.

## Scope

ZEUS CAST supports about 25 GAMDIAS devices: the CHIONE/AURA/ATLAS LCD AIOs,
AEOLUS P2 fan hubs, HELIOS P2, HERMES M7 and others. This project supports only
the BOREAS digital display, the only one it was tested on. The other
devices use different protocols, including LCD video streaming over HID or serial.
Each would need its own driver, and testing would need the hardware.

## Disclaimer

This is an unofficial project. It is not affiliated with or endorsed by GAMDIAS.
GAMDIAS, ZEUS CAST and BOREAS are trademarks of their owners and are used here only
to describe compatibility. No GAMDIAS code or assets are included in this repository.

## License

MIT. See [LICENSE](LICENSE).
