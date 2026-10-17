"""Command-line entry point: boreas-display <command>."""

import argparse
import logging
import sys
import time

from . import __version__, config, protocol, sensors
from .device import BoreasDisplay, DeviceError, find_devices


def cmd_list(args):
    devices = find_devices()
    if not devices:
        print("No BOREAS display found.")
        return 1
    for path, pid, name in devices:
        print(f"{path}  1b80:{pid:04x}  {name}")
    return 0


def cmd_info(args):
    with BoreasDisplay(args.device) as dev:
        info = dev.query_info()
    print(f"device:        {dev.path}")
    print(f"firmware:      {info.firmware}")
    print(f"default unit:  {'Celsius' if info.default_celsius else 'Fahrenheit'}")
    print(f"CPU temp mode: {'yes' if info.supports_cpu else 'no'}")
    print(f"fan RPM mode:  {'yes' if info.supports_fan else 'no'}")
    return 0


def cmd_sensors(args):
    s = config.load()
    cpu = sensors.find_cpu_temp(s.temp_sensor)
    fan = sensors.find_fan(s.fan_sensor)
    print("Temperature sensors:")
    for t in sensors.temp_sensors():
        mark = "*" if cpu and t.path == cpu.path else " "
        print(f" {mark} {t.id:<32} {t.read():6.1f} °C")
    print("Fan sensors:")
    fans = sensors.fan_sensors()
    if not fans:
        print("   (none - load a Super-I/O hwmon driver such as nct6775 or it87 for fan mode)")
    for f in fans:
        mark = "*" if fan and f.path == fan.path else " "
        print(f" {mark} {f.id:<32} {f.read():6.0f} RPM")
    print("\n* = used by the display. Override with: boreas-display config --temp-sensor/--fan-sensor")
    return 0


def _parse_digits(text):
    if len(text) != 4:
        raise argparse.ArgumentTypeError("give exactly 4 characters, digits or '_' for blank")
    out = []
    for ch in text:
        if ch == "_":
            out.append(None)
        elif ch.isdigit():
            out.append(int(ch))
        else:
            raise argparse.ArgumentTypeError(f"bad character {ch!r}")
    return out


def cmd_show(args):
    """Push a static value once (handy for testing). Stop the daemon first."""
    if args.digits:
        packet = protocol.raw_packet(args.digits, dot=args.dot, fahrenheit=args.unit == "f",
                                     mode=protocol.MODE_FAN if args.fan else protocol.MODE_TEMP,
                                     flash=args.flash)
    elif args.rpm is not None:
        packet = protocol.fan_packet(args.rpm, args.flash)
    else:
        packet = protocol.temp_packet(args.temp, args.unit == "f", args.flash)
    with BoreasDisplay(args.device) as dev:
        dev.send(packet)
        if args.hold:
            # Refresh at the daemon's cadence, as the Windows app streams frames continuously.
            try:
                while True:
                    time.sleep(0.5)
                    dev.send(packet)
            except KeyboardInterrupt:
                dev.send(protocol.without_flash(packet))
    return 0


def cmd_config(args):
    s = config.load()
    changed = False
    for key in ("mode", "unit", "interval", "temp_sensor", "fan_sensor", "device"):
        value = getattr(args, key)
        if value is not None:
            setattr(s, key, value)
            changed = True
    if args.alarm is not None:
        s.alarm = args.alarm == "on"
        changed = True
    if args.threshold is not None:
        s.alarm_threshold = args.threshold
        changed = True
    if changed:
        try:
            config.save(s)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"saved {config.config_path()} (a running daemon picks this up automatically)")
    for k, v in vars(s).items():
        print(f"{k:16} {v}")
    return 0


def cmd_run(args):
    from .daemon import Daemon
    Daemon().run()
    return 0


def cmd_gui(args):
    from .gui import main
    return main()


def build_parser():
    p = argparse.ArgumentParser(prog="boreas-display",
                                description="Linux driver for the GAMDIAS BOREAS digital display")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list connected displays").set_defaults(func=cmd_list)

    sp = sub.add_parser("info", help="query firmware/capabilities")
    sp.add_argument("--device", help="/dev/hidrawN (default: auto)")
    sp.set_defaults(func=cmd_info)

    sub.add_parser("sensors", help="list hwmon temperature/fan sensors").set_defaults(func=cmd_sensors)

    sp = sub.add_parser("run", help="run the update daemon in the foreground")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("show", help="display a fixed value (stop the daemon first)")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--temp", type=float, help="temperature in °C")
    g.add_argument("--rpm", type=float, help="fan speed")
    g.add_argument("--digits", type=_parse_digits, help="4 raw digits, '_' = blank, e.g. 1234")
    sp.add_argument("--unit", choices=("c", "f"), default="c")
    sp.add_argument("--dot", action="store_true", help="with --digits: show decimal point")
    sp.add_argument("--fan", action="store_true", help="with --digits: fan/RPM icons")
    sp.add_argument("--flash", action="store_true", help="blink")
    sp.add_argument("--hold", action="store_true", help="keep refreshing until Ctrl+C")
    sp.add_argument("--device")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("config", help="show or change settings")
    sp.add_argument("--mode", choices=("temp", "fan"))
    sp.add_argument("--unit", choices=("c", "f"))
    sp.add_argument("--alarm", choices=("on", "off"), help="flash when temperature >= threshold")
    sp.add_argument("--threshold", type=int, help="alarm threshold in the selected unit")
    sp.add_argument("--interval", type=float, help="update interval, seconds")
    sp.add_argument("--temp-sensor", help="'<chip>/<label>' from 'boreas-display sensors', '' = auto")
    sp.add_argument("--fan-sensor", help="'<chip>/<label>' from 'boreas-display sensors', '' = auto")
    sp.add_argument("--device", help="/dev/hidrawN, '' = auto")
    sp.set_defaults(func=cmd_config)

    sub.add_parser("gui", help="open the settings window (GTK 4)").set_defaults(func=cmd_gui)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        return args.func(args)
    except DeviceError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
