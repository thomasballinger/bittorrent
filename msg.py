import struct


msg_dict = {
        0 : 'choke',
        1 : 'unchoke',
        2 : 'interested',
        3 : 'not_interested',
        4 : 'have',
        5 : 'bitfield',
        6 : 'request',
        7 : 'piece',
        }

def keep_alive(): return '\x00' * 4
def choke(): return msg(0)
def unchoke(): return msg(1)
def interested(): return msg(2)
def not_interested(): return msg(3)
def have(piece_index): return msg(4, struct.pack('!I', piece_index)) #TODO zero-based index in what format?
def bitfield(bitfield): return msg(5, bitfield.tobytes())
def request(index, begin, length): return msg(6, struct.pack('!III', index, begin, length))
"""
def piece(index, begin, block)
def cancel(index, begin, length)
def port(listen_port)
"""
def msg(kind, *args):
    payload = ''.join(args)
    message_id = chr(kind)
    prefix = struct.pack('!I', len(message_id) + len(payload))
    return prefix + message_id + payload

def parse_message(self):
    """If a full message exists on the buffer, pull it off and return it

    If incomplete message, returns 'incomplete message'
    If nothing on buffer, returns None
    """
    temp = ''.join(self.buffer)
    print 'current buffer length:', len(temp)
    print 'front end of buffer:', repr(temp[:50])
    if len(temp) == 0:
        return None
    elif len(temp) >= 49 and temp[1:20] == 'BitTorrent protocol':
        l = ord(temp[0])
        protocol = temp[1:20]
        reserved = temp[20:28]
        info_hash = temp[28:48]
        peer_id = temp[48:68]
        self.buffer = [temp[68:]]
        return ('handshake', protocol, reserved, info_hash, peer_id)
    elif len(temp) >= 4:
        length = struct.unpack('!I', temp[:4])[0]
        if len(temp) < length + 4:
            print 'returning "incomplete message"',
            print '(looks like a', msg_dict[ord(temp[4])], 'message)'
            return 'incomplete message'
        self.buffer = [temp[length+4:]]
        if length == 0:
            return ('keepalive',)
        msg_id = ord(temp[4])
        kind = msg_dict[msg_id]
        if kind == 'bitfield':
            return ('bitfield', bitstring.BitArray(bytes=temp[5:length+4]))
        elif kind == 'piece':
            index, begin = struct.unpack('!II', temp[5:13])
            return ('piece', index, begin, temp[13:length+4])
        elif kind == 'have':
            (index,) = struct.unpack('!I', temp[5:9])
            return ('have', index)
        else:
            return kind,
    else:
        print 'received unknown or incomplete message, or perhaps prev parse consumed too much:'
        print repr(temp)
