"""
        print new.changes
Sparse (really Frequently Contiguous) Binary Array

TODO:
Eliminate need for .normalize() by ensuring self.changes never have duplicates
binary search to find overlapping segments

"""
import bisect
import sys
class SparseBitArray(object):
    """Sparse BitArray, in which data is represented by indices of changes
    between runs of set and unset values

    >>> s = SparseBitArray(20); s
    SparseBitArray('00000000000000000000')
    >>> s = SparseBitArray(iterable=[1,0,0,1], scale=3, repetitions=2); s
    SparseBitArray('111000000111111000000111')
    >>> s[:] = True; all(s), any(s)
    (True, True)
    """
    def __init__(self, length=None, iterable=None, scale=None, repetitions=None):
        self.cached_ones = None
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
            if isinstance(iterable, basestring):
                iterable = [int(x) for x in iterable]
            else:
                iterable = list(iterable)
            self.length = len(iterable)*scale*(repetitions)
            self.changes = []

            start = 0
            for i in range(repetitions):
                for x in iterable:
                    end = start + scale
                    self[start:end] = bool(x)
                    start += scale
    def all(self):
        self.normalize()
        return True if self.changes == [0, self.length] else False
    def none(self):
        self.normalize()
        return True if self.changes == [] else False
    def normalize(self):
        """Changes self.changes to the canonical representation

        >>> s = SparseBitArray(iterable='00000000000000000000')
        >>> s.changes = [0,0,0,0,20,20]
        >>> s.normalize()
        >>> s.changes
        []
        """
        if len(set(self.changes)) == len(self.changes):
            return
        i = 0
        while True:
            if i >= len(self.changes) - 1:
                break
            if self.changes[i] == self.changes[i+1]:
                del self.changes[i]
                del self.changes[i]
            else:
                i += 1

    def index(self, x):
        """Return index of element or raise ValueError if not found

        >>> s = SparseBitArray(iterable='0101')
        >>> s.index(0)
        0
        >>> s.index(1)
        1
        """
        if x and self.none():
            raise ValueError('no set bits in array')
        if (not x) and self.all():
            raise ValueError('no unset bits in array')
        x = bool(x)
        for i, el in enumerate(self):
            if bool(el) == x:
                return i
        raise Exception('Logic Error')

    def count(self, x):
        """counts true or false values
        >>> s = SparseBitArray(iterable=[1,0,0,1], scale=3, repetitions=2); s
        SparseBitArray('111000000111111000000111')
        >>> s.count(1)
        12
        >>> s.count(0)
        12
        >>> s[3:5] = 1; s.count(1)
        14
        >>> s.all(), s.none()
        (False, False)
        >>> s[:] = True; s.all()
        True
        >>> s[:] = False; s.none()
        True
        """
        if self.cached_ones is None:
            ones = 0
            last_one = None
            for i in self.changes:
                if last_one is None:
                    last_one = i
                else:
                    ones += i - last_one
                    last_one = None
            self.cached_ones = ones
        if x:
            return self.cached_ones
        else:
            return self.length - self.cached_ones

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

        >>> s = SparseBitArray(20); s[2:6] = True; s
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
            result = SparseBitArray(end - start)

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

        >>> s = SparseBitArray(20); s[2:6] = True; s
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
        self.cached_ones = None
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

    def __invert__(self):
        """bitwise inverse
        >>> a = SparseBitArray(20); a[4:6] = True; a[10:16] = True;
        >>> ~a
        SparseBitArray('11110011110000001111')
        >>> a = SparseBitArray(20); a[:] = True
        >>> ~a
        SparseBitArray('00000000000000000000')
        """
        new = SparseBitArray(self.length)
        new.changes = self.changes
        new.changes.append(self.length)
        new.changes.insert(0, 0)
        new.normalize()
        return new

    def __and__(self, other):
        """
        >>> a = SparseBitArray(20); a[4:6] = True; a[10:16] = True;
        >>> b = SparseBitArray(20); b[5:9] = True; b[11:18] = True;
        >>> a; b; a & b
        SparseBitArray('00001100001111110000')
        SparseBitArray('00000111100111111100')
        SparseBitArray('00000100000111110000')
        """
        self_index = 0
        other_index = 0
        new = SparseBitArray(self.length)
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
