"""Bytearray that immediately writes to disk"""
#TODO make this async? write are moderately fast
#TODO add a buffer? alternative to async
class DiskArray(object):
    def __init__(self, size, filename):
        self.f = open(filename, 'wb')
        self.f.write('')
        self.f.close()
        self.f = open(filename, 'r+b')
        self.length = size
    def __len__(self):
        return self.length
    def __setitem__(self, key, value):
        start, length = self._decode_slice(key)
        if len(value) != length:
            raise ValueError('bytes to be written do not match section size')
        self.f.seek(start)
        self.f.write(value)
        self.f.flush()
    def __getitem__(self, key):
        start, length = self._decode_slice(key)
        self.f.seek(start)
        return self.f.read(length)
    def _decode_slice(self, key):
        if isinstance(key, slice):
            start, step, end = key.start, key.step, key.stop
            if start is None: start = 0
            if end is None: end = len(self)
            if step not in [None, 1]: raise ValueError("Custom steps not allowed: "+repr(key))
            length = end - start
        else:
            start = key
            length = 1
        return start, length
