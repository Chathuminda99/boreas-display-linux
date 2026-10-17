"""Packets must match what the official Windows app sends."""

import unittest

from boreas_display import protocol as p


def body(packet):
    """Bytes [1..13] as the Windows code indexes them."""
    return list(packet[1:14])


class ProtocolTest(unittest.TestCase):
    def test_lengths(self):
        for pkt in (p.info_request(), p.temp_packet(40), p.fan_packet(1200)):
            self.assertEqual(len(pkt), 65)
            self.assertEqual(pkt[0], 0)
            self.assertEqual(pkt[14:], bytes(51))

    def test_info_request(self):
        # Info query: FF, four blanks, 0, 1, 1, 0, 0, checksum
        b = body(p.info_request())
        self.assertEqual(b[:12], [0x3A, 0xB5, 0xFF, 32, 32, 32, 32, 0, 1, 1, 0, 0])
        self.assertEqual(b[12], sum(b[:12]) & 0xFF)

    def test_temp_celsius(self):
        # Temperature mode, Celsius: dot=1, unit=1, cpu=1, mode byte 0
        self.assertEqual(body(p.temp_packet(45.6)),
                         [0x3A, 0xB5, 1, 32, 4, 5, 6, 1, 1, 1, 0, 0, 0x22])
        self.assertEqual(body(p.temp_packet(105.2))[3:7], [1, 0, 5, 2])

    def test_temp_fahrenheit(self):
        # 40 C -> 104.0 F, unit byte 0
        b = body(p.temp_packet(40, fahrenheit=True))
        self.assertEqual(b[3:11], [1, 0, 4, 0, 1, 0, 1, 0])
        # 20 C -> 68.0 F, leading blank
        self.assertEqual(body(p.temp_packet(20, fahrenheit=True))[3:7], [32, 6, 8, 0])

    def test_rounding_never_overflows_a_digit(self):
        # The original computed the tenths digit separately and could produce 10.
        for t in (45.97, 99.99, 0.05):
            self.assertTrue(all(d == 32 or 0 <= d <= 9 for d in body(p.temp_packet(t))[3:7]))
        self.assertEqual(body(p.temp_packet(45.97))[3:7], [32, 4, 6, 0])

    def test_fan(self):
        # Mode 1: dot=0, unit=0, cpu=0, mode byte 1
        self.assertEqual(body(p.fan_packet(1234))[3:12], [1, 2, 3, 4, 0, 0, 0, 1, 0])
        self.assertEqual(body(p.fan_packet(850))[3:7], [32, 8, 5, 0])
        self.assertEqual(body(p.fan_packet(123456))[3:7], [9, 9, 9, 9])

    def test_flash_and_stop_flash(self):
        on = p.temp_packet(95, flash=True)
        self.assertEqual(on[12], 1)
        off = p.without_flash(on)
        self.assertEqual(off[12], 0)
        self.assertEqual(off[13], p.checksum(off))
        self.assertEqual(off, p.temp_packet(95))

    def test_parse_info(self):
        # Reply observed from a real unit (firmware 1.0, CPU mode only).
        reply = bytes.fromhex("3ab5010100010100f3") + bytes(55)
        info = p.parse_info(reply)
        self.assertEqual(info.firmware, "1.0")
        self.assertTrue(info.default_celsius)
        self.assertTrue(info.supports_cpu)
        self.assertFalse(info.supports_fan)


if __name__ == "__main__":
    unittest.main()
