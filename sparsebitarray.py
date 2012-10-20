""""""

class SBA(object):
    """Sparse BitArray, in which data is represented by ranges

    >>> s = SBA(20); s
    <SparseBitArray of length 20, all bits cleared>
    >>> s[2:6] = True; s
    <SparseBitArray of length 20, [(2, 6)]>
    >>> s[4:10] = True; s
    <SparseBitArray of length 20, [(2, 10)]>
    >>> s[3:11] = False; s
    <SparseBitArray of length 20, [(2, 3)]>
    >>> s[4:14] = True; s
    <SparseBitArray of length 20, [(2, 3), (4, 14)]>
    >>> s[8:11] = False; s
    <SparseBitArray of length 20, [(2, 3), (4, 8), (11, 14)]>
    >>> s[5:7] = True; s
    <SparseBitArray of length 20, [(2, 3), (4, 8), (11, 14)]>
    >>> s[15:18] = False; s
    <SparseBitArray of length 20, [(2, 3), (4, 8), (11, 14)]>
    """
    def __init__(self, length):
        self.length = length
        self.set_ranges = []
    def __len__(self):
        return self.length
    def __repr__(self):
        s = '<SparseBitArray of length %d, ' % self.length
        if not self.set_ranges:
            s += 'all bits cleared>'
        elif self.set_ranges == [[0, self.length]]:
            s += 'all bits set>'
        else:
            s += str(self.set_ranges)+'>'
        return s
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
            elif start < r_start < end or start <= r_end < end:
                edge_overlapping.append((r_start, r_end))
            else:
                raise Exception("Logic Error!")
        return contained_by_new, edge_overlapping, contains_new

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            start, step, end = key.start, key.step, key.stop
            if step not in [None, 1]:
                raise ValueError("Custom steps not allowed: "+repr(key))
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
