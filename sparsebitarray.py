"""
Sparse (really Frequently Contiguous) Binary Array

TODO:
bitwise and would be really useful
generalize to more than two possible values
binary search to find overlapping segments

"""
class SBA(object):
    """Sparse BitArray, in which data is represented by ranges

    >>> s = SBA(20); s
    SparseBitArray('00000000000000000000')
    """
    def __init__(self, length):
        self.length = length
        self.set_ranges = []
    def __len__(self):
        return self.length
    def __repr__(self):
        s = ''.join(str(int(x)) for x in self)
        return 'SparseBitArray(\'%s\')' % s
    def _find_overlapping_ranges(self, start, end):
        """Returns existing ranges that overlap or touch a new one

        Returns a tuple of
          * ranges entirely contained by the new start and end
          * ranges over or at the edge of the new start and end
          * the range, if any, that entirely contains the new start and end
        """
        #TODO use binary search instead here
        edge_overlapping = []
        contained_by_new = []
        contains_new = None
        for r_start, r_end in self.set_ranges:
            if r_end < start or r_start > end:
                pass
            elif r_start <= start and r_end >= end:
                contains_new = (r_start, r_end)
                break
            elif r_start >= start and r_end <= end:
                contained_by_new.append((r_start, r_end))
            elif start <= r_start <= end or start <= r_end <= end:
                edge_overlapping.append((r_start, r_end))
            else:
                raise Exception("Logic Error!")
        return contained_by_new, edge_overlapping, contains_new

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
            start, step, end = key.start, key.step, key.stop
            if start is None: start = 0
            if end is None: end = len(self)
            if step not in [None, 1]: raise ValueError("Custom steps not allowed: "+repr(key))
            contained_by, edge_overlaps, contains = self._find_overlapping_ranges(start, end)
            result = SBA(end - start)
            if contains:
                result[:] = True
            for r_start, r_end in contained_by:
                result.set_ranges.append((r_start - start, r_end - start))
            for overlap_start, overlap_end in edge_overlaps:
                if overlap_end == start or overlap_start == end:
                    pass
                elif overlap_end < end:
                    result.set_ranges.append((0, overlap_end - start))
                elif overlap_start > start:
                    result.set_ranges.append((overlap_start - start, end - start))
                else:
                    raise Exception("Logic Error!")
            return result
        else:
            if not 0 <= key < self.length:
                raise IndexError
            contained_by, edge_overlaps, contains = self._find_overlapping_ranges(key, key+1)
            if contained_by or contains:
                return True
            else:
                return False

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
            start, step, end = key.start, key.step, key.stop
            if start is None: start = 0
            if end is None: end = len(self)
            if step not in [None, 1]: raise ValueError("Custom steps not allowed: "+repr(key))
            contained_by, edge_overlaps, contains = self._find_overlapping_ranges(start, end)
            if contains:
                if not value:
                    self.set_ranges.remove(contains)
                    self.set_ranges.append((contains[0], start))
                    self.set_ranges.append((end, contains[1]))
                return
            if value:
                for overlap_start, overlap_end in edge_overlaps:
                    if overlap_start < start:
                        start = overlap_start
                        self.set_ranges.remove((overlap_start, overlap_end))
                    elif overlap_end > end:
                        end = overlap_end
                        self.set_ranges.remove((overlap_start, overlap_end))
                    else:
                        raise Exception("Logic Error!")
            else:
                for overlap_start, overlap_end in edge_overlaps:
                    if overlap_start < start:
                        self.set_ranges.remove((overlap_start, overlap_end))
                        self.set_ranges.append((overlap_start, start))
                    elif overlap_end > end:
                        self.set_ranges.remove((overlap_start, overlap_end))
                        self.set_ranges.append((end, overlap_end))
                    else:
                        raise Exception("Logic Error!")
            for set_range in contained_by:
                self.set_ranges.remove(set_range)
            if value:
                self.set_ranges.append((start, end))
        else:
            raise ValueError("Single element assignment not allowed")

if __name__ == '__main__':
    import doctest
    print doctest.testmod()
