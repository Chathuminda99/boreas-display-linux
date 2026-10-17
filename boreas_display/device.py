"""hidraw access to the BOREAS display."""

import errno
import os
import select
from pathlib import Path

from . import protocol


class DeviceError(Exception):
    pass


def _hid_id(hidraw_name):
    """Return (vid, pid) for /sys/class/hidraw/<name>, or None."""
    uevent = Path("/sys/class/hidraw", hidraw_name, "device", "uevent")
    try:
        for line in uevent.read_text().splitlines():
            if line.startswith("HID_ID="):
                _bus, vid, pid = line[7:].split(":")
                return int(vid, 16), int(pid, 16)
    except (OSError, ValueError):
        pass
    return None


def find_devices():
    """List (path, pid, name) of every connected BOREAS display."""
    found = []
    root = Path("/sys/class/hidraw")
    if not root.is_dir():
        return found
    for entry in sorted(root.iterdir()):
        ids = _hid_id(entry.name)
        if ids and ids[0] == protocol.VENDOR_ID and ids[1] in protocol.PRODUCT_IDS:
            found.append((f"/dev/{entry.name}", ids[1], protocol.PRODUCT_IDS[ids[1]]))
    return found


class BoreasDisplay:
    def __init__(self, path=None):
        if path is None:
            devices = find_devices()
            if not devices:
                raise DeviceError("no GAMDIAS BOREAS display found (USB 1b80:b53a / 1b80:b554)")
            path = devices[0][0]
        self.path = path
        try:
            self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError:
            raise DeviceError(f"permission denied on {path}; install the udev rule "
                              "(see README) or run with sudo") from None
        except OSError as e:
            raise DeviceError(f"cannot open {path}: {e.strerror}") from None

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def write(self, packet):
        try:
            os.write(self.fd, packet)
        except OSError as e:
            if e.errno in (errno.ENODEV, errno.EIO, errno.ESHUTDOWN):
                raise DeviceError("device disconnected") from None
            raise

    def read(self, timeout=0.1):
        """Read one input report (64 bytes) or return None on timeout."""
        r, _, _ = select.select([self.fd], [], [], timeout)
        if not r:
            return None
        try:
            return os.read(self.fd, 64)
        except BlockingIOError:
            return None
        except OSError as e:
            if e.errno in (errno.ENODEV, errno.EIO):
                raise DeviceError("device disconnected") from None
            raise

    def _drain(self):
        while self.read(0) is not None:
            pass

    def send(self, packet, ack_timeout=0.1):
        """Write a report and consume the device's acknowledgement, like the Windows app."""
        self._drain()
        self.write(packet)
        return self.read(ack_timeout)

    def query_info(self):
        self._drain()
        self.write(protocol.info_request())
        # The Windows app waits 500 ms before reading the reply.
        reply = self.read(0.6)
        if reply is None:
            raise DeviceError("no reply to info request")
        return protocol.parse_info(reply)
