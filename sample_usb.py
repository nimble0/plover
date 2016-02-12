import usb.core
import usb.util
import sys

# find a Stenograph device
devicenumber = 12
dev = None
while (dev is None) and (devicenumber > 0):
    dev = usb.core.find(idVendor=0x112b, idProduct=devicenumber)
    devicenumber -= 1


# was it found?
if dev is None:
    raise ValueError('Device not found')

# set the active configuration. With no arguments, the first
# configuration will be the active one
dev.set_configuration()

# get an endpoint instance
cfg = dev.get_active_configuration()
intf = cfg[(0, 0)]

epout = usb.util.find_descriptor(
    intf,
    # match the first OUT endpoint
    custom_match = \
    lambda e: \
    usb.util.endpoint_direction(e.bEndpointAddress) == \
    usb.util.ENDPOINT_OUT)

assert epout is not None

epin = usb.util.find_descriptor(
    intf,
    # match the first IN endpoint
    custom_match = \
    lambda e: \
    usb.util.endpoint_direction(e.bEndpointAddress) == \
    usb.util.ENDPOINT_IN)

assert epin is not None


for cfg in dev:
    sys.stdout.write(str(cfg.bConfigurationValue) + '\n')
    for intf in cfg:
        sys.stdout.write('\t' + \
                         str(intf.bInterfaceNumber) + \
                         ',' + \
                         str(intf.bAlternateSetting) + \
                         '\n')
        for ep in intf:
            sys.stdout.write('\t\t' + \
                             str(ep.bEndpointAddress) + \
                             '\n')

# From Stenograph USB Writer protocol
#         0     1  2  3  4  5    6  7    8  9 10 11  12 13 14 15  16    17 18 19
#         S     G  Sequence   | Action | data len   | FileOffset | ByteCount      | param 3   | param 4   | param 5
pkt = [0x53, 0x47, 0, 0, 0, 0, 0x13, 0,  0, 0, 0, 0,  0, 0, 0, 0,  0x08, 0x0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
# Create bytearray from list of integers.
packet = bytearray(pkt)

offset8byte_steno_time = 0

# write the data
for i in range(1, 0x7fffff):  # this loop is just for testing, make a real loop with callbacks
    # update sequence number (0 to 255 works fine)
    packet[2] = (i & 255)

    # read from this offset
    packet[12] = (offset8byte_steno_time & 255)
    packet[13] = ((offset8byte_steno_time >> 8) & 255)
    packet[14] = ((offset8byte_steno_time >> 16) & 255)
    packet[15] = ((offset8byte_steno_time >> 24) & 255)


    try:
        epout.write(packet)
        data = epin.read(128, 3000) # we only asked for 8 bytes (1 stroke) - so we are only expecting 40 bytes here.
    except:
        data = None
        pass
    if data is not None:
        if len(data) > 32:
            # got some steno, process it.
            #
            # First 32 bytes is the response header.  Then the steno follows
            #
            # Byte 0: 11H#STKP where H is stenomark and # is the numeral bar.
            # Byte 1: 11WHRAO*
            # Byte 2: 11EUFRPB
            # Byte 3: 11LGTSDZ
            # Bytes 4-7: 'timestamp'
            #
            #
            # update steno offset
            offset8byte_steno_time += (len(data) - 32)
    print offset8byte_steno_time