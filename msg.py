r"""
msg.py: a leaner bittorrent peer message class, based on
https://github.com/jschneier/bittorrent/blob/master/message.py
and
https://github.com/kristenwidman/Bittorrenter/blob/master/messages.py

>>> import msg
>>> a = msg.Have(index=1); a
Have(index=1)
>>> a = msg.Have(index=1); a
Have(index=1)
>>> str(a)
'\x00\x00\x00\x05\x04\x00\x00\x00\x01'
>>> a.index_ # underscore so we don't get str.index
1
>>> a = msg.Have(index=5); a.index_
5
>>> msg.Have(bytestring='\x00\x00\x00\x05\x04\x00\x00\x00\x03\x01')
(Have(index=3), '\x01')
>>> Msg(bytestring="\x00\x00\x00\x00")
(KeepAlive(), '')
>>> str(Msg(bytestring="\x00\x00\x00\x00")[0])
'\x00\x00\x00\x00'
>>> a = Piece(index=1, begin=0, block='asdf'); a, str(a)
(Piece(index=1, begin=0, block='asdf'), '\x00\x00\x00\r\x07\x00\x00\x00\x01\x00\x00\x00\x00asdf')
>>> str(a)
'\x00\x00\x00\r\x07\x00\x00\x00\x01\x00\x00\x00\x00asdf'
>>> len(a)
17
>>> m = KeepAlive()
>>> 2*m + m[2:3] + (m + 'a') + ('a' + m) + m*2
'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00aa\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
>>> Handshake(info_hash='a'*20, peer_id='b'*20)
Handshake(pstr='BitTorrent protocol', reserved='\x00\x00\x00\x00\x00\x00\x00\x00', info_hash='aaaaaaaaaaaaaaaaaaaa', peer_id='bbbbbbbbbbbbbbbbbbbb')
>>> Bitfield(bitfield='\x00\x01')
Bitfield(bitfield='\x00\x01')
>>> Bitfield('\x00\x01')
Bitfield(bitfield='\x00\x01')
"""

import re
import struct
from collections import OrderedDict

message_info = {
        'KeepAlive' :  {'msg_id' : None},
        'Choke' :         {'msg_id' : 0,
            '__doc__' : "Notification that receiver is being choked"},
        'Unchoke' :       {'msg_id' : 1},
        'Interested' :    {'msg_id' : 2},
        'NotInterested' : {'msg_id' : 3},
        'Have' :          {'msg_id' : 4,
            'protocol_args' : ['index']},
        'Bitfield' :      {'msg_id' : 5,
            'protocol_extended' : 'bitfield'},
        'Request' :       {'msg_id' : 6,
            'protocol_args' : [ 'index', 'begin', 'length' ]},
        'Piece' :         {'msg_id' : 7,
            'protocol_args' : ['index', 'begin'],
            'protocol_extended' : 'block'},
        'Cancel' :        {'msg_id' : 8,
            'protocol_args' : ['index', 'begin', 'length']},
        'Port' :          {'msg_id' : 9,
            'protocol_extended' : 'listen_port'}
        }

class Msg(str):
    """Implements behavior for all messages but Handshake
        when subclassed, provide class attributes for:
        protocol_args     (if not implemented, will use base class - [])
        protocol_extended (if not implemented, will use base class - None)
        msg_id (this should be a single byte)
    """
    protocol_args = []
    protocol_extended = None

    def __new__(cls, **kwargs):
        if 'bytestring' in kwargs:
            buff = kwargs['bytestring']
            if len(buff) < 4:
                return None, buff
            (msg_length,) = struct.unpack('!I', buff[0:4])
            if len(buff) >= 68 and buff[:11] == '\x13BitTorrent':
                return Handshake(bytestring=buff)
            if len(buff) < msg_length + 4:
                return None, buff
            msg_id = ord(buff[4]) if len(buff) > 4 else None
            (actual_cls,) = [msg_cls for msg_cls in message_classes.values() if msg_cls.msg_id == msg_id]
            if cls is Msg:
                return actual_cls.__new__(actual_cls, **kwargs)
            else:
                assert actual_cls == cls
                return actual_cls.__new_from_buffer(kwargs['bytestring'])
        elif set(cls.protocol_args + ([cls.protocol_extended] if cls.protocol_extended else [])) == set(kwargs.keys()):
            return cls.__new_from_args(kwargs)
        else:
            raise Exception("Bad init values")

    @classmethod
    def __new_from_buffer(cls, byte_buffer):
        if len(byte_buffer) < 4:
            return None, byte_buffer
        (msg_length,) = struct.unpack('!I', byte_buffer[0:4])
        if len(byte_buffer) < msg_length + 4:
            return None, byte_buffer
        return str.__new__(cls, byte_buffer[:msg_length+4]), byte_buffer[msg_length+4:]

    @classmethod
    def __new_from_args(cls, kwargs):
        if cls is Handshake:
            return Handshake.__new__(**kwargs)
        s = ''
        if cls.msg_id is not None:
            s += chr(cls.msg_id)
        for arg_name in cls.protocol_args:
            s += struct.pack('!I', kwargs[arg_name])
        if cls.protocol_extended:
            s += kwargs[cls.protocol_extended]
        s = struct.pack('!I', len(s)) + s
        return str.__new__(cls, s)

    def __repr__(self):
        payload = self[5:]
        args = []
        for arg_name in self.protocol_args:
            args.append('%s=%d' % (arg_name, struct.unpack('!I', payload[:4])[0]))
            payload = payload[4:]
        if self.protocol_extended:
            args.append('%s=%s' % (self.protocol_extended, repr(payload)))
        return '%s(%s)' % (self.__class__.__name__, ', '.join(args))

    def __getattr__(self, att):
        if att.endswith('_') and len(att) > 1:
            att = att[:-1]
        if self.protocol_extended == att:
            return self[5+len(self.protocol_args)*4:]
        try:
            i = self.protocol_args.index(att)
            (value,) = struct.unpack('!I', self[(5+i*4):(5+(i+1)*4)])
            return value
        except ValueError:
            return AttributeError('object has no attribute \'%s\'' % att)

    @property
    def kind(self):
        """return class name, but converted from CamelCase to camel_case"""
        # copied from http://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-camel-case
        # because I was lazy
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', self.__class__.__name__)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

#TODO This class is terrible - mixed levels of abstraction, repeated information, just awful
class Handshake(Msg):
    r"""
    >>> data = '\x13BitTorrent protocol\x00\x00\x00\x00\x00\x10\x00\x05\xef\\\xce\x17v\xb19\x14.F\xb5\x1dE\xe7\xedN\x84\xbc\xdam-DE1220-lgEiZoSZxQ!g'
    >>> Handshake(bytestring=data)
    (Handshake(pstr='BitTorrent protocol', reserved='\x00\x00\x00\x00\x00\x10\x00\x05', info_hash='\xef\\\xce\x17v\xb19\x14.F\xb5\x1dE\xe7\xedN\x84\xbc\xdam', peer_id='-DE1220-lgEiZoSZxQ!g'), '')
    """
    positions = OrderedDict((
        ('l'         , slice(0, 1)),
        ('pstr'      , slice(1, 20)),
        ('reserved'  , slice(20, 28)),
        ('info_hash' , slice(28, 48)),
        ('peer_id'   , slice(48, 68)),
        ))
    def __new__(cls, pstr='BitTorrent protocol', reserved='\x00\x00\x00\x00\x00\x00\x00\x00', info_hash=None, peer_id=None, **kwargs):
        if 'bytestring' in kwargs:
            bytestring = kwargs['bytestring']
            if not len(bytestring) >= 49+19 and bytestring[1:20] == 'BitTorrent protocol':
                raise ValueError()
            values = [kwargs['bytestring'][slice_] for att, slice_ in list(cls.positions.iteritems())[1:]]
            return Handshake(*values), kwargs['bytestring'][68:]
        kwargs['pstr'] = pstr
        kwargs['reserved'] = reserved
        kwargs['info_hash'] = info_hash
        kwargs['peer_id'] = peer_id
        if set(kwargs) - set(cls.positions.keys()[1:]):
            raise ValueError('Extra Arguments to Handshake init:' + repr(kwargs))
        (s,) = struct.pack('!B', len(kwargs['pstr']))
        assert len(s) == 1
        for att, slice_ in list(cls.positions.iteritems())[1:]:
            if len(kwargs[att]) != slice_.stop - slice_.start:
                raise ValueError('argument wrong length: '+att+' '+repr(kwargs[att]))
            s += kwargs[att]
        return str.__new__(Handshake, s)

    def __init__(self, pstr='BitTorrent protocol', reserved='\x00\x00\x00\x00\x00\x00\x00\x00', info_hash=None, peer_id=None):
        pass

    def __repr__(self):
        signature = 'pstr=%r, reserved=%r, info_hash=%r, peer_id=%r' % (self[1:20], self[20:28], self[28:48], self[48:68])
        return '%s(%s)' % (self.__class__.__name__, signature)

    def __getattr__(self, att):
        if att.endswith('_') and len(att) > 1:
            att = att[:-1]
        if self.protocol_extended == att:
            return self[5+len(self.protocol_args)*4:]
        try:
            i = self.protocol_args.index(att)
            return struct.unpack('!I', self[5+i*4:5+(i+1)*4])[0]
        except ValueError:
            return AttributeError('object has no attribute \'%s\'' % att)

    @property
    def kind(self):
        """return class name, but converted from CamelCase to camel_case"""
        return 'handshake'

def parse_messages(buff):
    r"""
    >>> data = '\x13BitTorrent protocol\x00\x00\x00\x00\x00\x10\x00\x05\xef\\\xce\x17v\xb19\x14.F\xb5\x1dE\xe7\xedN\x84\xbc\xdam-DE1220-lgEiZoSZxQ!g\x00\x00\x00\x0f\x05\xff\xfb\xda\xfc\xff\xff\xff\xfd\xf3\xff\xff\x7f\xff\xe0\x00\x00\x00\x05\x04\x00\x00\x00\r\x00\x00\x00\x05\x04\x00\x00\x00\x12\x00\x00\x00\x05\x04\x00\x00\x00\x15\x00\x00\x00\x05\x04\x00\x00\x00\x17\x00\x00\x00\x05\x04\x00\x00\x00\x1e\x00\x00\x00\x05\x04\x00\x00\x00\x1f\x00\x00\x00\x05\x04\x00\x00\x00>\x00\x00\x00\x05\x04\x00\x00\x00D\x00\x00\x00\x05\x04\x00\x00\x00E\x00\x00\x00\x05\x04\x00\x00\x00X\x00\x00\x00\x01\x01'
    >>> data = '\x13BitTorrent protocol\x00\x00\x00\x00\x00\x10\x00\x05\xef\\\xce\x17v\xb19\x14.F\xb5\x1dE\xe7\xedN\x84\xbc\xdam-DE1220-lgEiZoSZxQ!g'
    >>> parse_messages(data)
    ([Handshake(pstr='BitTorrent protocol', reserved='\x00\x00\x00\x00\x00\x10\x00\x05', info_hash='\xef\\\xce\x17v\xb19\x14.F\xb5\x1dE\xe7\xedN\x84\xbc\xdam', peer_id='-DE1220-lgEiZoSZxQ!g')], '')
    """

    messages = []
    while True:
        m, buff = Msg(bytestring=buff)
        if not m:
            break
        messages.append(m)
    return messages, buff

message_classes = {}
for msg in message_info:
    class_dict = {}
    for att in ['msg_id', 'protocol_args', 'protocol_extended']:
        if att in message_info[msg]:
            class_dict[att] = message_info[msg][att]
    klass = type(msg, (Msg,), class_dict)

    ###############################################
    # Creating an init signature for each message
    #
    # This is an api, so class initializer signatures are important!
    # But Python <3.3 has no way to dynamically create signatures besides eval!
    # see http://stackoverflow.com/questions/1409295/set-function-signature-in-python
    # ipython and bpython both use the init method for suggesting arguments
    args = klass.protocol_args
    last_arg = klass.protocol_extended
    signature = ', '.join(['self'] +
            ['%s=0' % x for x in
                args + ([last_arg] if last_arg else [])] +
            ['**kwargs'])
    __init__ = None # we're about to redefine it
    code = "def __init__({signature}): pass".format(signature=signature)
    exec(code)
    class_dict['__init__'] = __init__

    # A custom __new__ allows keyword args to be passed positionally
    args_for_new = ', '.join(['self'] +
            ['%s=%s' % (x, x) for x in
                args + ([last_arg] if last_arg else [])] +
            ['**kwargs'])
    __new__ = None
    code = """def __new__({signature}):
        return Msg.__new__({args_for_new})""".format(signature=signature, args_for_new=args_for_new)
    exec(code)
    class_dict['__new__'] = __new__

    # end dynamic __init__ hack
    ##############################################

    klass = type(msg, (Msg,), class_dict)
    message_classes[msg] = klass

locals().update(message_classes)

def test():
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == '__main__':
    test()
