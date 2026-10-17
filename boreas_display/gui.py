"""GTK 4 settings window (replaces the BoreasDigital WPF page).

The window only edits the config file and controls the systemd user service;
the daemon owns the device, so both never write to it at the same time.
"""

import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from . import config, sensors  # noqa: E402
from .device import find_devices  # noqa: E402

SERVICE = "boreas-display.service"


def _systemctl(*args):
    try:
        return subprocess.run(["systemctl", "--user", *args], capture_output=True,
                              text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="BOREAS Display")
        self.set_default_size(380, -1)
        self.settings = config.load()
        self._loading = True

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        self.set_child(box)

        self.readout = Gtk.Label(css_classes=["title-1"])
        self.readout.set_markup("<span size='xx-large' font_family='monospace'>--.-</span>")
        box.append(self.readout)
        self.device_label = Gtk.Label(css_classes=["dim-label"])
        box.append(self.device_label)

        grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        box.append(grid)

        grid.attach(Gtk.Label(label="Display", xalign=0), 0, 0, 1, 1)
        self.mode_temp = Gtk.CheckButton(label="CPU temperature")
        self.mode_fan = Gtk.CheckButton(label="Fan RPM", group=self.mode_temp)
        mode_box = Gtk.Box(spacing=8)
        mode_box.append(self.mode_temp)
        mode_box.append(self.mode_fan)
        grid.attach(mode_box, 1, 0, 1, 1)
        if not sensors.fan_sensors():
            self.mode_fan.set_sensitive(False)
            self.mode_fan.set_tooltip_text("No hwmon fan sensor found (load nct6775/it87)")

        grid.attach(Gtk.Label(label="Unit", xalign=0), 0, 1, 1, 1)
        self.unit_c = Gtk.CheckButton(label="°C")
        self.unit_f = Gtk.CheckButton(label="°F", group=self.unit_c)
        unit_box = Gtk.Box(spacing=8)
        unit_box.append(self.unit_c)
        unit_box.append(self.unit_f)
        grid.attach(unit_box, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label="High-temp alarm", xalign=0), 0, 2, 1, 1)
        alarm_box = Gtk.Box(spacing=8)
        self.alarm = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.threshold = Gtk.SpinButton.new_with_range(0, 250, 1)
        self.alarm_unit = Gtk.Label()
        alarm_box.append(self.alarm)
        alarm_box.append(self.threshold)
        alarm_box.append(self.alarm_unit)
        grid.attach(alarm_box, 1, 2, 1, 1)

        svc_box = Gtk.Box(spacing=8)
        self.svc_label = Gtk.Label(xalign=0, hexpand=True)
        self.svc_button = Gtk.Button()
        self.svc_button.connect("clicked", self._toggle_service)
        svc_box.append(self.svc_label)
        svc_box.append(self.svc_button)
        box.append(svc_box)

        s = self.settings
        (self.mode_fan if s.mode == "fan" else self.mode_temp).set_active(True)
        (self.unit_f if s.unit == "f" else self.unit_c).set_active(True)
        self.alarm.set_active(s.alarm)
        self.threshold.set_value(s.alarm_threshold)
        for w in (self.mode_temp, self.unit_c):
            w.connect("toggled", self._changed)
        self.alarm.connect("notify::active", self._changed)
        self.threshold.connect("value-changed", self._changed)
        self._loading = False

        self._refresh()
        GLib.timeout_add(1000, self._refresh)

    def _changed(self, *_):
        if self._loading:
            return
        s = self.settings
        s.mode = "temp" if self.mode_temp.get_active() else "fan"
        s.unit = "c" if self.unit_c.get_active() else "f"
        s.alarm = self.alarm.get_active()
        s.alarm_threshold = int(self.threshold.get_value())
        config.save(s)
        self._refresh()

    def _refresh(self):
        s = self.settings
        unit = "°F" if s.unit == "f" else "°C"
        self.alarm_unit.set_text(unit)
        if s.mode == "fan":
            fan = sensors.find_fan(s.fan_sensor)
            rpm = fan.read() if fan else None
            text = f"{int(rpm):4d} RPM" if rpm is not None else "---- RPM"
            alarm = False
        else:
            t = sensors.find_cpu_temp(s.temp_sensor)
            c = t.read() if t else None
            if c is None:
                text, alarm = "--.-" + unit, False
            else:
                v = c * 1.8 + 32 if s.unit == "f" else c
                text = f"{v:5.1f}{unit}"
                alarm = s.alarm and v >= s.alarm_threshold
        color = "#e01b24" if alarm else "#3584e4"
        self.readout.set_markup(f"<span size='xx-large' font_family='monospace' "
                                f"foreground='{color}'>{GLib.markup_escape_text(text)}</span>")

        devices = find_devices()
        self.device_label.set_text(", ".join(f"{n} ({p})" for p, _, n in devices)
                                   if devices else "No BOREAS display connected")

        r = _systemctl("is-active", SERVICE)
        active = r is not None and r.stdout.strip() == "active"
        self.svc_label.set_text("Background service: " + ("running" if active else "stopped"))
        self.svc_button.set_label("Stop" if active else "Start")
        self.svc_button.set_sensitive(r is not None)
        return True

    def _toggle_service(self, _btn):
        r = _systemctl("is-active", SERVICE)
        active = r is not None and r.stdout.strip() == "active"
        res = _systemctl("stop" if active else "start", SERVICE)
        if res is not None and res.returncode != 0:
            dialog = Gtk.AlertDialog(message="Could not change the service",
                                     detail=res.stderr.strip() or "Is boreas-display installed? Run install.sh.")
            dialog.show(self)
        self._refresh()


def main():
    app = Gtk.Application(application_id="io.github.chathuminda99.BoreasDisplay")
    app.connect("activate", lambda a: Window(a).present())
    return app.run(sys.argv[:1])
