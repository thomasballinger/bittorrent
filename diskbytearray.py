"""Bytearray that immediately writes to disk"""
import logging
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
        logging.info('%s write start: %d, length: %d', repr(self), start, length)
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
    def __setitem__(self, key, value):
        start, length = self._decode_slice(key)
        if len(value) != length:
            raise ValueError('bytes to be written do not match section size')
        logging.info('%s write start: %d, length: %d', repr(self), start, length)
        start_file_index = bisect.bisect_right(self.starts, start) - 1
        logging.info('start file index: %d', start_file_index)
        written = 0
        for file_index in range(start_file_index, len(self.files)):
            file_location = self.starts[file_index]
            file_size = self.sizes[file_index]
            da = self.diskarrays[file_index]

            start_in_file = start - file_location + written
            desired_write_end = start_in_file + length - written
            file_end_pos = min(desired_write_end, file_size)
            da[start_in_file:file_end_pos] = value[written:written+(file_end_pos-start_in_file)]
            written += file_end_pos - start_in_file

            if desired_write_end <= file_size:
                break
    def __getitem__(self, key):
        start, length = self._decode_slice(key)
        start_file_index = bisect.bisect_right(self.starts, start) - 1
        data = ''
        for file_index in range(start_file_index, len(self.files)):
            file_location = self.starts[file_index]
            file_size = self.sizes[file_index]
            da = self.diskarrays[file_index]

            start_in_file = start - file_location + len(data)
            desired_read_end = start_in_file + length - len(data)
            file_end_pos = min(desired_read_end, file_size)
            data += da[start_in_file:file_end_pos]

            if desired_read_end <= file_size:
                break
        return data

if __name__ == '__main__':
    a = DiskArray(100, '/tmp/somthing')
    a[40:45] = '\x00\x00\x00\x00e'
    a = MultiFileDiskArray([10,10,10], ['a', 'b', 'c'])
    s = 'abcdefghijklmno'
    #a[:15] = 'abcdefghijklmno'
    #print a[0:15] == s

    print len(a)
    a[5:25] = 'abcdefghijklmnopqrst'
    print a[5:25]
    print len(a)

