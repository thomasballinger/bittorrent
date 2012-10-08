"""Msg - Bittorrent tcp client connection messages

Desired api:

msg.keep_alive()  # acts like a keepalive message
msg.have(1)    # acts like a have second piece message

msg.Msg('\x00\x00\x00\x05\x04\x00\x00\x00\x03')
# creates a have message

msg.Msg('have', 1)
# creats a have message

msg.from_string('\x00\x00\x00\x00\x00\x00\x00\x05')
# returns an array of messages, plus the unparsed portion of the string
(Msg('\x00\x00\x00\x00'),), 4

msg.from_stream('\x00\x00\x00\x00\x00\x00\x00\x05')
# returns an array of messages, plus how many bytes were converted
(Msg('\x00\x00\x00\x00'),), 4

msg.from_strings(['\x00\x00\x00\x00\x00\x00', \x00\x05'])
# returns an array of messages, plus the position of the first byte not parsed
(Msg('\x00\x00\x00\x00'),), (1, 4)

Msg.kind == 'have'

Msg.kind = 'notmodifiable'
exception of some kind; attributeError?
# bytestrings also nonmodifiable - no wait modifiable but the Msg gets reinitialized

str:
<Have Msg: index=1>

repr:
Msg('\x00\x00\x00\x00')

==: compares byte strings

"""

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
        8 : 'cancel',
        9 : 'port',
        }

args_dict = {
        'keep_alive' : (),
        'choke' : (),
        'unchoke' : (),
        'intersted' : (),
        'not_interested' : (),
        'have' : ('index',),
        'bitfield' : ('bitfield',),
        'request' : ('index', 'begin', 'length'),
        'piece' : ('index', 'begin', 'block'),
        'cancel' : ('index', 'begin', 'length'),
        'port' : ('port',),
        'handshake' : ('pstr', 'reserved', 'info_hash', 'peer_id'),
        }

class Msg(object):
    r"""A bittorrent tcp peer connection message.

    >>> repr(Msg("\x00\x00\x00\x00"))
    


    """
    def __init__(self, kind_or_bytestring=None, **kwargs):
        self._atts_modified = False
        self._atts_dict = {}
        if 'kind' in kwargs:
            if kind_or_bytestring:
                raise TypeError("Specify a kind once or specify a bytestring")
            kind_or_bytestring = kwargs['kind']
            del kwargs['kind']
        print '---'
        print repr(kind_or_bytestring)
        print repr(args_dict.keys())
        print '---'
        if kind_or_bytestring in args_dict:
            self.init_from_args(kind_or_bytestring, **kwargs)
        elif len(kwargs) == 0:
            self.init_from_bytestring(kind_or_bytestring)
        else:
            raise TypeError("__init__() takes a string of bytes or kw arguments" )
    def init_from_args(self, kind, **kwargs):
        self.kind = kind
        if self.kind == 'handshake':
            self._atts_dict['pstr'] = kwargs.get('pstr', 'BitTorrent Protocol')
            self._atts_dict['reserved'] = kwargs.get('reserved', '\x00\x00\x00\x00\x00\x00\x00\x00')
            self.info_hash = kwargs['info_hash']
            self.peer_id = kwargs['peer_id']
        elif self.kind in args_dict:
            if set(args_dict[self.kind]) != set(kwargs.values()):
                print 'warning: extra kwargs not being used:', set(kwargs.values()) - set(args_dict[self.kind])
            for arg in args_dict[self.kind]:
                setattr(self, arg, kwargs[arg])
        else:
            raise TypeError("kind must be an allowed message kind")
    def init_from_bytestring(self, bytestring):
        msg, rest = parse_message(bytestring)
        if rest:
            print rest
            raise Exception('Bad init string; extra: '+repr(rest))
        #TODO pass in kwargs instead of a real Msg object
        print msg

    def _get_kind(self): return self.__dict__['kind']
    def _set_kind(self, value): raise AttributeError("kind of Msg is not modifiable")
    kind = property(_get_kind, _set_kind)

    def _get_bytestring(self):
        if self.atts_modified:
            self._bytestring = getattr(self, '_'+self.kind)()
            self.atts_modified = False
        return self._bytestring
    def _set_bytestring(self, value):
        # todo: set the bytestring, then reinitialize
        raise Exception("Not Yet Implemented")
    bytestring = property(_get_bytestring, _set_bytestring)

    def __setattr__(self, item, value):
        if 'kind' in self.__dict__ and item in args_dict[self.kind]:
            self.atts_modified = True
            raise Exception("Not Yet Implemented")
        else:
            self.__dict__[item] = value

    def _keep_alive(self): return '\x00' * 4
    def _choke(self): return msg(0)
    def _unchoke(self): return msg(1)
    def _interested(self): return msg(2)
    def _not_interested(self): return msg(3)
    def _have(self): return msg(4, struct.pack('!I', self.piece_index))
    def _bitfield(self):
        try:
            s = self.bitfield.tobytes()
        except AttributeError:
            s = self.bitfield
        return msg(5, s)
    def _request(self): return msg(6, struct.pack('!III', self.index, self.begin, self.length))
    def _piece(self): return msg(7, struct.pack('!III', self.index, self.begin, self.block))
    def _cancel(self): return msg(8, struct.pack('!III', self.index, self.begin, self.length))
    def _port(self): return msg(9, struct.pack('!III', self.port))

    def _msg(kind, args):
        payload = ''.join(args)
        message_id = chr(kind)
        prefix = struct.pack('!I', len(message_id) + len(payload))
        return prefix + message_id + payload

    # Make Msg's behave like strings in most cases
    def __getattr__(self, att):
        def func_help(*args, **kwargs):
            result = getattr(self.s, att)(*args, **kwargs)
            return result
        return func_help

    def __repr__(self):
        return 'Msg('+self.bytestring+')'

    def __str__(self):
        return self.bytestring

def parse_message(buff):
    """If a full message exists in input s, pull it off and return a msg object, along with unparsed portion of the string

    If incomplete message, returns 'incomplete message'
    If nothing on buffer, returns None
    """
    if len(buff) == 0:
        return None, ''
    elif len(buff) >= 49 and buff[1:20] == 'BitTorrent protocol':
        l = ord(buff[0])
        protocol = buff[1:20]
        reserved = buff[20:28]
        info_hash = buff[28:48]
        peer_id = buff[48:68]
        rest = buff[68:]
        return Msg('handshake', protocol=protocol, reserved=reserved, info_hash=info_hash, peer_id=peer_id), rest
    elif len(buff) >= 4:
        length = struct.unpack('!I', buff[:4])[0]
        if len(buff) < length + 4:
            print 'returning "incomplete message"',
            print '(looks like a', msg_dict[ord(buff[4])], 'message)'
            return 'incomplete message'
        rest = buff[length+4:]
        if length == 0:
            return Msg('keep_alive'), rest
        msg_id = ord(buff[4])
        kind = msg_dict[msg_id]
        if kind == 'bitfield':
            return Msg('bitfield', bitfield=buff[5:length+4]), rest
        elif kind == 'piece':
            index, begin = struct.unpack('!II', buff[5:13])
            return Msg('piece', index=index, begin=begin, piece=buff[13:length+4]), rest
        elif kind == 'have':
            (index,) = struct.unpack('!I', buff[5:9])
            return Msg('have', index=index), rest
        else:
            return Msg(kind), rest
    else:
        print 'received unknown or incomplete message, or perhaps prev parse consumed too much:'
        print repr(buff)

def test():
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == '__main__':
    test()
