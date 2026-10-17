"""Background loop that keeps the display updated."""

import logging
import signal
import threading

from . import config, protocol, sensors
from .device import BoreasDisplay, DeviceError, find_devices

log = logging.getLogger("boreas-display")

RECONNECT_DELAY = 2.0


class Daemon:
    def __init__(self, config_file=None):
        self.config_file = config_file or config.config_path()
        self.stop_event = threading.Event()
        self.settings = config.load(self.config_file)
        self._config_mtime = self._mtime()
        self._last_frame = None

    def _mtime(self):
        try:
            return self.config_file.stat().st_mtime_ns
        except OSError:
            return None

    def _reload_if_changed(self):
        m = self._mtime()
        if m != self._config_mtime:
            self._config_mtime = m
            self.settings = config.load(self.config_file)
            log.info("config reloaded: %s", self.settings)

    def build_frame(self):
        """Return (packet, description) for the current sensor readings."""
        s = self.settings
        fahrenheit = s.unit == "f"
        if s.mode == "fan":
            fan = sensors.find_fan(s.fan_sensor)
            rpm = fan.read() if fan else None
            # The Windows app never flashes in fan mode.
            return protocol.fan_packet(rpm or 0), f"{int(rpm or 0)} RPM"

        temp = sensors.find_cpu_temp(s.temp_sensor)
        celsius = temp.read() if temp else None
        if celsius is None:
            return protocol.temp_packet(0, fahrenheit), "no sensor"
        shown = celsius * 1.8 + 32 if fahrenheit else celsius
        flash = s.alarm and shown >= s.alarm_threshold
        desc = f"{shown:.1f}°{'F' if fahrenheit else 'C'}" + (" ALARM" if flash else "")
        return protocol.temp_packet(celsius, fahrenheit, flash), desc

    def _session(self, dev):
        try:
            info = dev.query_info()
            log.info("connected %s, firmware %s (cpu=%s fan=%s)", dev.path,
                     info.firmware, info.supports_cpu, info.supports_fan)
        except DeviceError as e:
            log.warning("info query failed on %s: %s", dev.path, e)
        while not self.stop_event.is_set():
            self._reload_if_changed()
            packet, desc = self.build_frame()
            dev.send(packet)
            if packet != self._last_frame:
                log.debug("display: %s", desc)
                self._last_frame = packet
            self.stop_event.wait(self.settings.interval)
        # Like the Windows app on exit: leave the last value, not blinking.
        if self._last_frame:
            dev.send(protocol.without_flash(self._last_frame))

    def run(self):
        signal.signal(signal.SIGTERM, lambda *_: self.stop_event.set())
        signal.signal(signal.SIGINT, lambda *_: self.stop_event.set())
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, lambda *_: setattr(self, "_config_mtime", -1))
        waiting_logged = False
        while not self.stop_event.is_set():
            path = self.settings.device or None
            if path is None and not find_devices():
                if not waiting_logged:
                    log.info("waiting for BOREAS display to be connected...")
                    waiting_logged = True
                self.stop_event.wait(RECONNECT_DELAY)
                self._reload_if_changed()
                continue
            waiting_logged = False
            try:
                with BoreasDisplay(path) as dev:
                    self._session(dev)
            except DeviceError as e:
                log.warning("%s; retrying in %.0fs", e, RECONNECT_DELAY)
                self.stop_event.wait(RECONNECT_DELAY)
                self._reload_if_changed()
        log.info("stopped")
