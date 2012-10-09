"""Msg - Bittorrent tcp client connection messages

Desired api:

msg.keep_alive()  # acts like a keepalive message
'\x00\x00\x00\x00'
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

    >>> Msg("\x00\x00\x00\x00")
    Msg('keep_alive')
    >>> str(Msg("\x00\x00\x00\x00"))
    '\x00\x00\x00\x00'
    >>> a = Msg("piece", index=1, begin=0, block='asdf'); a
    Msg('piece', index=1, begin=0, block='asdf')
    >>> a.index = 3; a
    Msg('piece', index=3, begin=0, block='asdf')
    >>> str(a)
    '\x00\x00\x00\r\x07\x00\x00\x00\x03\x00\x00\x00\x00asdf'
    >>> a.kind = 'asdf'; a.kind
    'piece'
    >>> len(a)
    17

    """
    def __init__(self, kind_or_bytestring=None, **kwargs):
        self._atts_modified = False
        self._atts_dict = {}
        if 'kind' in kwargs:
            if kind_or_bytestring:
                raise TypeError("Specify a kind once or specify a bytestring")
            kind_or_bytestring = kwargs['kind']
            del kwargs['kind']
        if kind_or_bytestring in args_dict:
            self.init_from_args(kind_or_bytestring, **kwargs)
        elif len(kwargs) == 0:
            self.init_from_bytestring(kind_or_bytestring)
        else:
            raise TypeError("__init__() takes a string of bytes or kw arguments" )
    def init_from_args(self, kind, **kwargs):
        self.__dict__['_kind'] = kind
        if self.kind == 'handshake':
            self.pstr = kwargs.get('pstr', 'BitTorrent Protocol')
            self.reserved = kwargs.get('reserved', '\x00\x00\x00\x00\x00\x00\x00\x00')
            self.info_hash = kwargs['info_hash']
            self.peer_id = kwargs['peer_id']
        elif self.kind in args_dict:
            for arg in args_dict[self.kind]:
                try:
                    setattr(self, arg, kwargs[arg])
                except KeyError:
                    raise TypeError("__init__() for "+self.kind+" Msg requires "+arg )
            if set(args_dict[self.kind]) != set(kwargs.keys()):
                print 'warning: extra kwargs not being used:', set(kwargs.keys()) - set(args_dict[self.kind])
        else:
            raise TypeError("kind must be an allowed message kind")
    def init_from_bytestring(self, bytestring):
        msg, rest = parse_message(bytestring)
        self.__dict__['_kind'] = msg.kind
        for dep in args_dict[msg.kind]:
            setattr(self, dep, getattr(msg, dep))
        if rest:
            print rest
            raise Exception('Bad init string; extra: '+repr(rest))
        self._bytestring = bytestring
        #TODO pass in kwargs instead of a real Msg object


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
    def _piece(self): return msg(7, struct.pack('!II', self.index, self.begin), self.block)
    def _cancel(self): return msg(8, struct.pack('!III', self.index, self.begin, self.length))
    def _port(self): return msg(9, struct.pack('!III', self.port))


    # Make Msg's behave like strings in most cases
    def __getattr__(self, att):
        if att in dir(str):
            if callable(getattr(str, att)):
                def func_help(*args, **kwargs):
                    result = getattr(self.s, att)(*args, **kwargs)
                    return result
                return func_help
            else:
                return getattr(self.s, att)
        elif att in args_dict[self.kind]:
            return self._atts_dict[att]

    def __setattr__(self, item, value):
        if '_kind' in self.__dict__ and item in args_dict[self.kind]:
            self.atts_modified = True
            #setattr(self, item, value)
            self.__dict__[item] = value
        else:
            self.__dict__[item] = value

    def _get_kind(self): return self.__dict__['_kind']
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

    # todo try to kill this method and let it use the str one
    def __len__(self):
        return len(self.bytestring)

    def __repr__(self):
        s = 'Msg(\''+self.kind+'\''
        if args_dict[self.kind]:
            s += ', '
        s += ', '.join([att+'='+repr(getattr(self, att)) for att in args_dict[self.kind]])
        s += ')'
        return s

    def __str__(self):
        return self.bytestring

def msg(kind, *args):
    """Returns a msg bytestring from message id and args"""
    payload = ''.join(args)
    message_id = chr(kind)
    prefix = struct.pack('!I', len(message_id) + len(payload))
    return prefix + message_id + payload

def parse_message(buff):
    r"""If a full message exists in input s, pull it off and return a msg object, along with unparsed portion of the string

    If incomplete message, returns 'incomplete message'
    If nothing on buffer, returns None

    >>> parse_message('\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01')
    (Msg('keep_alive'), '\x00\x00\x00\x00\x00\x00\x00\x01')
    >>> parse_message(parse_message('\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01')[1])
    (Msg('keep_alive'), '\x00\x00\x00\x01')
    >>> parse_message('\x00\x00\x00\x01')
    ('incomplete message', '\x00\x00\x00\x01')

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
            return 'incomplete message', buff
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

# global convenience functions
def keep_alive(): return Msg('keep_alive')
def choke(): return Msg('choke')
def unchoke(): return Msg('unchoke')
def interested(): return Msg('interested')
def not_interested(): return Msg('not_interested')
def have(index): return Msg('have', index=index)
def bitfield(bitfield): return Msg('bitfield', bitfield=bitfield)
def request(index, begin, length): return Msg(index=index, begin=begin, length=length)
def piece(index, begin, block): return Msg(index=index, begin=begin, block=block)
def cancel(index, begin, length): Msg(index=index, begin=begin, length=length)
def port(port): return Msg(port=port)
def handshake(pstr=None, reserved=None, info_hash=None, peer_id=None):
    if pstr is None: pstr = 'BitTorrent Protocol'
    if reserved is None: pstr = '\x00\x00\x00\x00\x00\x00\x00\x00'
    x = Msg('handshake', pstr=pstr, reserved=reserved, info_hash=info_hash, peer_id=peer_id)
    print repr(x)
    return x

def test():
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == '__main__':
    test()
