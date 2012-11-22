"""
msg2.py: a leaner bittorrent peer message class, based on
https://github.com/jschneier/bittorrent/blob/master/message.py
and
https://github.com/kristenwidman/Bittorrenter/blob/master/messages.py

>>> import msg2 as msg
>>> a = msg.Have(index=1); a
Have(index=1)
>>> a.index_
1
"""

import struct

class Msg(str):
    """This is for everything but Handshake
        If you subclass this, you should provide class attributes for:
        protocol_args     (if not implemented, will use base class - [])
        protocol_extended (if not implemented, will use base class - None)
        msg_id (this should be a single byte)
    """
    protocol_args = []
    protocol_extended = None

    def __new__(cls, **kwargs):
        print 'calling new with', kwargs
        if 'byte_buffer' in kwargs:
            buff = kwargs['byte_buffer']
            if len(buff) < 4:
                return None, buff
            msg_length = struct.unpack('!I', buff[0:4])
            if len(buff) < msg_length + 4:
                return None, buff
            if len(buff) >= 68 and buff[:11] == '\x13BitTorrent':
                return Handshake(buff[:68]), buff[68:]
            msg_id = ord(buff[4]) if len(buff) > 4 else None
            actual_cls = message_classes[MSG_NUMS[msg_id]] #TODO get rid of MSG_NUMS
            if cls is Msg:
                return actual_cls.__new__(**kwargs)
            else:
                assert actual_cls == cls
                return Msg.__new_from_buffer(kwargs)
        elif set(cls.protocol_args + ([cls.protocol_extended] if cls.protocol_extended else [])) == set(kwargs.keys()):
            return cls.__new_from_args(kwargs)
        else:
            print 'stuff from message class', set(cls.protocol_args + [cls.protocol_extended] if cls.protocol_extended else [])
            print 'kwargs', set(kwargs.keys())
            raise Exception("Bad init values")

    @classmethod
    def __new_from_buffer(cls, byte_buffer):
        if len(byte_buffer) < 4:
            return None, byte_buffer
        msg_length = struct.unpack('!I', byte_buffer[0:4])
        if len(byte_buffer) < msg_length + 4:
            return None, byte_buffer
        payload = byte_buffer[5:]
        for arg_name in cls.protocol_args:
            setattr(cls, arg_name, payload[:4])
            payload = payload[4:]
        if cls.protocol_extended:
            setattr(cls, cls.protocol_extended, payload)

    @classmethod
    def __new_from_args(cls, kwargs):
        s = ''
        if cls.msg_id != '':
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
            args.append('%s=%d' % (arg_name, struct.unpack('!I', payload[:4])[0]))
        return '%s(%s)' % (self.__class__.__name__, ', '.join(args))

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
            'protocol_args' : ['bitfield']},
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

message_classes = {}
for msg in message_info:
    class_dict = {}
    for att in ['msg_id', 'protocol_args', 'protocol_extended']:
        if att in message_info[msg]:
            class_dict[att] = message_info[msg][att]
    # This is an api, so function/initializer signatures are important!
    # But Python <3.3 has no way to dynamically create signatures besides eval!
    # see http://stackoverflow.com/questions/1409295/set-function-signature-in-python
    # ipython and bpython both use the init method for suggesting arguments
    args = class_dict.get('protocol_args', [])
    last_arg = class_dict.get('protocol_extended', None)
    signature = ', '.join('%s=0' % x for x in (args + [last_arg] if last_arg else []))
    func = None # we're about to redefine it
    code = "def __new__({signature}): pass".format(signature=signature)
    exec(code)
    class_dict['__new__'] = func

    klass = type(msg, (Msg,), class_dict)
    message_classes[msg] = klass

locals().update(message_classes)
MSG_NUMS = {message_info[msg]['msg_id'] : msg for msg in message_info}


def test():
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == '__main__':
    test()
