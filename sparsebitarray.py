"""
Sparse (really Frequently Contiguous) Binary Array

TODO:
ensure all(a[10:20]) works
bitwise and would be really useful
binary search to find overlapping segments
faster all implementation
count(True)
cache count(True) and count(False)
Construct from bitarray and multiplier

"""
import bisect
import sys
class SBA(object):
    """Sparse BitArray, in which data is represented by indices of changes
    between runs of set and unset values

    >>> s = SBA(20); s
    SparseBitArray('00000000000000000000')
    >>> s = SBA(iterable=[1,0,0,1], scale=3, repetitions=2); s
    SparseBitArray('111000000111111000000111')
    """
    def __init__(self, length=None, iterable=None, scale=None, repetitions=None):
        if (not length and not iterable) or (length and iterable):
            raise ValueError("Must initialize with either length or iterable")
        if length and (scale is not None or repetitions is not None):
            raise ValueError("repate and scale can't be used with length")
        if length:
            self.length = length
            self.changes = []
        else:
            scale = scale if scale is not None else 1
            repetitions = repetitions if repetitions is not None else 1
            iterable = list(iterable)
            self.length = len(iterable)*scale*(repetitions)
            self.changes = []

            start = 0
            for i in range(repetitions):
                for x in iterable:
                    end = start + scale
                    self[start:end] = bool(x)
                    start += scale

    def __len__(self):
        return self.length
    def __repr__(self):
        s = ''.join(str(int(x)) for x in self)
        return 'SparseBitArray(\'%s\')' % s
    def _decode_slice(self, key):
        start, step, end = key.start, key.step, key.stop
        if start is None: start = 0
        if end is None: end = len(self)
        if step not in [None, 1]: raise ValueError("Custom steps not allowed: "+repr(key))
        return start, end
    def _indices(self, start, end):
        start_index = bisect.bisect_right(self.changes, start)
        end_index = bisect.bisect_left(self.changes, end)
        return start_index, end_index

    def __getitem__(self, key):
        """Get a slice or the value of an entry

        >>> s = SBA(20); s[2:6] = True; s
        SparseBitArray('00111100000000000000')
        >>> s[2:6]
        SparseBitArray('1111')
        >>> s[4:10]
        SparseBitArray('110000')
        >>> s[9:14] = True; s[17:19] = True; s
        SparseBitArray('00111100011111000110')
        >>> s[2:18]
        SparseBitArray('1111000111110001')
        >>> s[1], s[10]
        (False, True)
        """
        if isinstance(key, slice):
            start, end = self._decode_slice(key)
            start_index, end_index = self._indices(start, end)
            result = SBA(end - start)

            if self[start]:
                result.changes.append(0)

            result.changes.extend( change - start for change in self.changes[start_index:end_index] )

            return result
        else:
            if key >= len(self):
                raise IndexError(key)

            return bool(bisect.bisect_right(self.changes, key) % 2)

    def __setitem__(self, key, value):
        """Sets item or slice to True or False

        >>> s = SBA(20); s[2:6] = True; s
        SparseBitArray('00111100000000000000')
        >>> s[4:10] = True; s
        SparseBitArray('00111111110000000000')
        >>> s[3:11] = False; s
        SparseBitArray('00100000000000000000')
        >>> s[4:14] = True; s
        SparseBitArray('00101111111111000000')
        >>> s[8:11] = False; s
        SparseBitArray('00101111000111000000')
        >>> s[5:7] = True; s
        SparseBitArray('00101111000111000000')
        >>> s[15:18] = False; s
        SparseBitArray('00101111000111000000')
        >>> s[14:16] = False; s
        SparseBitArray('00101111000111000000')
        >>> s[14:16] = True; s
        SparseBitArray('00101111000111110000')
        >>> s[4:] = True; s
        SparseBitArray('00101111111111111111')
        >>> s[:10] = False; s
        SparseBitArray('00000000001111111111')
        >>> s[:] = False; s
        SparseBitArray('00000000000000000000')
        >>> s[:] = True; s
        SparseBitArray('11111111111111111111')
        """
        if isinstance(key, slice):
            start, end = self._decode_slice(key)
            start_index, end_index = self._indices(start, end)

            new_changes = self.changes[:start_index]

            if bool(len(new_changes) % 2) != value:
                new_changes.append(start)

            if bool(end_index % 2) != value:
                new_changes.append(end)

            new_changes.extend(self.changes[end_index:])

            self.changes = new_changes
        else:
            raise ValueError("Single element assignment not allowed")
    def __and__(self, other):
        """
        >>> a = SBA(20); a[4:6] = True; a[10:16] = True;
        >>> b = SBA(20); b[5:9] = True; b[11:18] = True;
        >>> a; b; a & b
        SparseBitArray('00001100001111110000')
        SparseBitArray('00000111100111111100')
        SparseBitArray('00000100000111110000')
        """
        self_index = 0
        other_index = 0
        new = SBA(self.length)
        state = False
        while True:
            self_num = self.changes[self_index] if self_index < len(self.changes) else sys.maxint
            other_num = other.changes[other_index] if other_index < len(other.changes) else sys.maxint
            if self_num == other_num == sys.maxint:
                break
            if self_num <= other_num:
                cur = self_num
                self_index += 1
                if self_num == other_num:
                    continue
            else:
                cur = other_num
                other_index += 1
            if bool(self_index % 2) and bool(other_index % 2) and not state:
                new.changes.append(cur)
                state = True
            elif state and not bool(self_index % 2 or not bool(other_index % 2)):
                new.changes.append(cur)
                state = False
        return new

if __name__ == '__main__':
    import doctest
    print doctest.testmod()
