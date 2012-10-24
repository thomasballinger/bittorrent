"""Bytearray that immediately writes to disk"""
import os
import bisect
#TODO make this async? write are moderately fast
#TODO add a buffer? alternative to async
class DiskArray(object):
    def __init__(self, size, filename):
        try:
            os.makedirs(os.path.dirname(filename))
        except OSError:
            pass
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
class MultiFileDiskArray(DiskArray):
    def __init__(self, sizes, files):
        self.sizes = sizes
        self.files = files
        self.starts = [sum(self.sizes[:(i)]) for i in range(len(self.sizes))]
        self.diskarrays = [DiskArray(size, fn) for size, fn in zip(sizes, files)]
        self.length = sum(sizes)
        print self.sizes
        print self.files
        print self.starts
    def __setitem__(self, key, value):
        start, length = self._decode_slice(key)
        if len(value) != length:
            raise ValueError('bytes to be written do not match section size')
        start_file_index = bisect.bisect_left(self.starts, start)
        written = 0
        for file_index in range(start_file_index, len(self.files)):
            file_location = self.starts[file_index]
            file_size = self.sizes[file_index]
            da = self.diskarrays[file_index]

            start_in_file = start - file_location + written
            desired_write_end = start_in_file + length - written
            file_end_pos = min(desired_write_end, file_size)
            print start_in_file
            print file_end_pos
            print value[written:written+(file_end_pos-start_in_file)]
            da[start_in_file:file_end_pos] = value[written:written+(file_end_pos-start_in_file)]

            if desired_write_end <= file_size:
                break
    def __getitem__(self, key):
        start, length = self._decode_slice(key)
        start_file_index = bisect.bisect_left(self.starts, start)
        data = ''
        for file_index in range(start_file_index, len(self.files)):
            file_location = self.starts[file_index]
            file_size = self.sizes[file_index]
            da = self.files[file_index]

            start_in_file = start - file_location + len(data)
            desired_write_end = start_in_file + length - len(data)
            file_end_pos = min(desired_write_end, file_size)
            print 'start', start_in_file
            print 'end', file_end_pos
            print 'data', da[0:10]
            data += da[start_in_file:file_end_pos]

            if desired_write_end <= file_size:
                break
        return data

if __name__ == '__main__':
    a = MultiFileDiskArray([10,10,10], ['a', 'b', 'c'])
    a[:10] = 'abcdefghij'
    print a[0:10]
