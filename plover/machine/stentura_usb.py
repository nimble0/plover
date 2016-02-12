# Copyright (c) 2013 Hesky Fisher
# See LICENSE.txt for details.

# TODO: add tests

"Stentura USB Protocol"

import sys
from plover import log

if sys.platform.startswith('win32'):
    from plover.machine.base import StenotypeBase
    from pywinusb import hid
else:
    from plover.machine.base import ThreadedStenotypeBase as StenotypeBase
    import hid

# Note: "H" is the Stenomark
STENO_KEY_CHART = (('', '', 'H', '#', 'S-', 'T-', 'K-', 'P-'),
                   ('', '', 'W-', 'H-', 'R-', 'A-', 'O-', '*'),
                   ('', '', '-E', '-U', '-F', '-R', '-P', '-B'),
                   ('', '', '-L', '-G', '-T', '-S', '-D', '-Z'))
# Bytes 4 through 7 are a timestamp.

def packet_to_stroke(p):
   keys = []
   for i, b in enumerate(p):
       map = STENO_KEY_CHART[i]
       for i in xrange(8):
           if (b >> i) & 1:
               key = map[-i + 7]
               if key:
                   keys.append(key)
   return keys

VENDOR_ID = 0x112b
DEVICE_IDS = range(1, 13)

EMPTY = [0] * 4

class DataHandler(object):

    def __init__(self, callback):
        self._callback = callback
        self._pressed = EMPTY

    def update(self, p):
        if p == EMPTY and self._pressed != EMPTY:
            stroke = packet_to_stroke(self._pressed)
            if stroke:
                self._callback(stroke)
            self._pressed = EMPTY
        else:
            self._pressed = [x[0] | x[1] for x in zip(self._pressed, p)]


class Stenotype(StenotypeBase):

    # From Stenograph USB Writer protocol
    #         0     1  2  3  4  5    6  7    8  9 10 11  12 13 14 15  16    17 18 19
    #         S     G  Sequence   | Action | data len   | FileOffset | ByteCount      | param 3   | param 4   | param 5
    pkt = [0x53, 0x47, 0, 0, 0, 0, 0x13, 0,  0, 0, 0, 0,  0, 0, 0, 0,  0x08, 0x0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    # Create bytearray from list of integers.
    write_packet = bytearray(pkt)
    machine_offset = 0

    def __init__(self, params):
        super(Stenotype, self).__init__()
        self._machine = None

    if sys.platform.startswith('win32'):

        def start_capture(self):
            """Begin listening for output from the stenotype machine."""
            devices = hid.HidDeviceFilter(vendor_id=VENDOR_ID).get_devices()
            if len(devices) == 0:
                log.info('Stentura USB: no devices with vendor id %s', str(VENDOR_ID))
                log.warning('Stentura USB not connected')
                self._error()
                return
            self._machine = devices[0]
            self._machine.open()
            handler = DataHandler(self._notify)

            def callback(p):
                if len(p) != 8: return
                handler.update(p[:4])

            self._machine.set_raw_data_handler(callback)
            self._ready()

    else:

        def start_capture(self):
            """Begin listening for output from the stenotype machine."""
            try:
                if hasattr(hid.device, 'open'):
                    # Probably this loop
                    self._machine = hid.device()
                    for i in DEVICE_IDS:
                        try:
                            self._machine.open(VENDOR_ID, i)
                            continue
                        except IOError as e:
                            # 1/12 chance says we threw an exception.
                            if i is 12:
                                raise
                else: # Legacy loop
                    for i in DEVICE_IDS:
                        try:
                            self._machine = hid.device(VENDOR_ID, i)
                            continue
                        except IOError as e:
                            # 1/12 chance says we threw an exception.
                            if i is 12:
                                raise
                self._machine.set_nonblocking(0)
            except IOError as e:
                log.info('Stentura USB device not found: %s', str(e))
                log.warning('Stentura (USB) is not connected')
                self._error()
                return
            super(Stenotype, self).start_capture()

        def run(self):
            handler = DataHandler(self._notify)
            self._ready()
            loop = 0x00
            while not self.finished.isSet():
                self.write_packet[2] = (loop & 255)
                loop += 0x01

                # read from this offset
                self.write_packet[12] = (self.machine_offset & 255)
                self.write_packet[13] = ((self.machine_offset >> 8) & 255)
                self.write_packet[14] = ((self.machine_offset >> 16) & 255)
                self.write_packet[15] = ((self.machine_offset >> 24) & 255)

                data = self._machine.read(40)
                if len(data) <= 32: continue
                self.machine_offset += (len(data) - 32) # Always 8 ?!
                # We only care about 33, 34, 35, 36.
                handler.update(self.write_packet[33, 37])

    def stop_capture(self):
        """Stop listening for output from the stenotype machine."""
        super(Stenotype, self).stop_capture()
        if self._machine:
            self._machine.close()
        self._stopped()


if __name__ == '__main__':
    from plover.steno import Stroke
    import time
    def callback(s):
        print Stroke(s).rtfcre
    machine = Stenotype()
    machine.add_callback(callback)
    machine.start_capture()
    time.sleep(30)
    machine.stop_capture()
