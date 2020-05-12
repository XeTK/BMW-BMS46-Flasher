from serial import Serial, EIGHTBITS, PARITY_EVEN, STOPBITS_ONE
from progress.bar import Bar
from fire import Fire

ROM_SIZE_KB = 256

CHUNK_SIZE = 0x64 # 100 Bytes long.

DME_ID = 0x12
DME_COMMAND = 0x06

# Example packet structure
# Get Bytes 0x0 0x64
#     12 09 06 00 00 00 00 64 79                        .......dy   
# 0Xffffff 0x64
#     12 09 06 00 ff ff ff 40 a2                        ....ÿÿÿ@¢        

# Some images have the endianness flipped.
def correct_byte_order(data_bytes_incoming):
    data_bytes = bytearray(data_bytes_incoming)

    length = len(data_bytes)
    half_length = int(length /2 ) 
    # remainder = length % half_length
    # print(length, half_length, remainder)


    for i in range(half_length):
        index = i * 2
        next = index + 1
        temp = data_bytes[index]
        data_bytes[index] = data_bytes[next]
        data_bytes[next] = temp

    return data_bytes

# Create XOR checksum for data package.
def calculate_checksum(packet_bytes):
    checksum = 0x0
    for el in packet_bytes:
        checksum ^= el
    return checksum

# Construct message, to send over K-CAN.
def get_chunk(address, chunk_size):
    address_bytes = address.to_bytes(4, byteorder='big')

    data = bytearray(address_bytes)
    data += bytearray([chunk_size])

    result = build_command(DME_ID, DME_COMMAND, data)
    # print(result.hex())

    return result

# Construct full message.
def build_command(ecu, command, data):
    length = len(data) + 4
    data = bytearray([ecu, length, command]) + data
    checksum = calculate_checksum(data)
    data += bytearray([checksum])

    return data

# Send command and process responce
def read(command, com_port, flipped):
    command_length = len(command)

    com_port.write(command)
    com_port.flush()

    # Get how long the responce payload is.
    # Response contains original command, we take the length of that then read the first 2 bytes after that.
    # Byte 2 contains the length of whole packet.
    get_size_buffer = com_port.read(command_length + 2) 
    get_length_byte = get_size_buffer[-1:] # get last byte
    remaining_length = ord(get_length_byte) # Byte to Int
    remaining_length -= 2 # We have already read 2 bytes of the payload.

    get_rest_of_buffer = com_port.read(remaining_length) 

    valid_data = get_rest_of_buffer[1:-1] # strip command from front, and checksum from end.

    if flipped: # If we want the endianness swapped.
        valid_data = correct_byte_order(valid_data)

    return valid_data


# Main application runner.
def run(com="COM1", baudrate=9600, filename="ecu.bin", flipped=False):
    serial_port = Serial(
        com, 
        baudrate, 
        EIGHTBITS, 
        PARITY_EVEN, 
        STOPBITS_ONE, 
        timeout=None, 
        xonxoff=False,
        rtscts=False, 
        write_timeout=None, 
        dsrdtr=False, 
        inter_byte_timeout=None, 
        exclusive=None
    )

    number_of_bytes = ROM_SIZE_KB * 1024

    chunks = int(number_of_bytes / CHUNK_SIZE)

    remainder = number_of_bytes % chunks

    print(ROM_SIZE_KB, CHUNK_SIZE, number_of_bytes, chunks, remainder)


    buffer = bytearray()

    bar = Bar('Reading', max=chunks)
    # Get all full sized chunks.
    for chunk in range(chunks):
        address = chunk * CHUNK_SIZE
        command = get_chunk(address, CHUNK_SIZE)
        result = read(command, serial_port, flipped)
        buffer.extend(result)
        bar.next()

    bar.finish()

    # Get remainder.
    if remainder != 0:
        address = number_of_bytes - remainder
        command = get_chunk(address, remainder)
        result = read(command, flipped)
        buffer.extend(result)

    # Write to file.
    f = open(filename, 'w+b')
    f.write(buffer)
    f.close()

# Entry point.
if __name__ == '__main__':
    Fire(run)
