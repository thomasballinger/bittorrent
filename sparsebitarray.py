"""
Sparse (really Frequently Contiguous) Binary Array

TODO:
Eliminate need for .normalize() by ensuring self.changes never have duplicates
binary search to find overlapping segments

"""
import operator
import bisect
import collections
import sys
class SparseArray(object):
    """Abstract class for code shared between Sparse Arrays"""
    def __init__(self, length=None, iterable=None, scale=None, repetitions=None, default=None):
        if (length is None and iterable is None) or (length is not None and iterable is not None):
            raise ValueError("Must initialize with either length or iterable")
        if length is not None and (scale is not None or repetitions is not None):
            raise ValueError("repate and scale can't be used with length")
        if length is not None:
            self.length = length
            self._initialize_structures()
            if default is not None:
                self[:] = default
        else:
            scale = scale if scale is not None else 1
            repetitions = repetitions if repetitions is not None else 1
            if isinstance(iterable, basestring):
                iterable = [int(x) for x in iterable]
            else:
                iterable = list(iterable)
            self.length = len(iterable)*scale*(repetitions)

            self._initialize_structures()

            start = 0
            for i in range(repetitions):
                for x in iterable:
                    end = start + scale
                    self[start:end] = x
                    start += scale

    def __len__(self):
        return self.length

    def _decode_slice(self, key):
        start, step, end = key.start, key.step, key.stop
        if start is None: start = 0
        if end is None: end = len(self)
        if end == sys.maxint: end = len(self)
        if step not in [None, 1]: raise ValueError("Custom steps not allowed: "+repr(key))
        return start, end

    def _indices(self, start, end):
        start_index = bisect.bisect_right(self.changes, start)
        end_index = bisect.bisect_left(self.changes, end)
        return start_index, end_index

def _apply_sparsearraywise(f):
    """Creates a function which will combine two arrays elementwise given a function f

    """
    def arraywise_function(self, other):
        print >> sys.stderr, 'calling arraywise function on', self, 'and', other
        if not isinstance(other, self.__class__):
            other = self.__class__(self.length, default=other)
        print >> sys.stderr, self.changes, other.changes
        self_index = 0
        other_index = 0
        new = self.__class__(self.length)
        cur = 0
        while True:
            self_num = self.changes[self_index] if self_index < len(self.changes) else len(self)
            other_num = other.changes[other_index] if other_index < len(other.changes) else len(self)
            if self_num == other_num == len(self):
                break
            if self_num <= other_num:
                old_cur = cur
                cur = self_num
                self_index += 1
                if self_num == other_num:
                    continue
            else:
                old_cur = cur
                cur = self_num
                other_index += 1
                if cur == old_cur:
                    continue
            new[old_cur:cur] = f(self[old_cur], other[old_cur])
        return new
    return arraywise_function

class SparseObjectArray(SparseArray):
    """Sparse Array of Objects, in which data is represented by indices of
    changes from one value to another

    >>> a = SparseObjectArray(2, default=frozenset([7])); a
    SparseObjectArray([frozenset([7]), frozenset([7])])
    >>> b = SparseObjectArray(2, default=frozenset()); b[1:2] = frozenset([1,2,3]);
    >>> b
    SparseObjectArray([frozenset([]), frozenset([1, 2, 3])])
    >>> a.arraywise(frozenset.union, b)
    SparseObjectArray([frozenset([7]), frozenset([7])])
    >>> a.union(b)
    SparseObjectArray([frozenset([7]), frozenset([7])])
    >>> SparseObjectArray(2)
    SparseObjectArray([None, None])
    >>> a = SparseObjectArray(4, default=0); a
    SparseObjectArray([0, 0, 0, 0])
    >>> a[1:3]
    SparseObjectArray([0, 0])
    >>> a[1:3] = 1; a
    SparseObjectArray([0, 1, 1, 0])
    >>> a = SparseObjectArray(4, default=0)

    #>>> a[1:3].changes
    #[0]

    #>>> a[1:3] + 1; a
    #SparseObjectArray([1, 1])
    """
    def __init__(self, *args, **kwargs):
        super(SparseObjectArray, self).__init__(*args, **kwargs)

    def _initialize_structures(self):
        self.values = [None]
        self.changes = [0]
        self.runs = collections.defaultdict(set)
        self.runs[None].add((0, self.length))

    def arraywise(self, f, other):
        """Apply any 2-argument function arraywise.

        >>> a = SparseObjectArray(4, default=2)
        >>> b = SparseObjectArray(4, default=3)
        >>> import operator
        >>> a.arraywise(operator.lt, b)
        SparseObjectArray([True, True, True, True])
        """
        g = _apply_sparsearraywise(f)
        return g(self, other)

    union = _apply_sparsearraywise(frozenset.union)
    __add__ = _apply_sparsearraywise(operator.add)

    def __sub__(self, other):
        """For combining two arrays elementwise, not for extending arrays"""
        raise Exception("not Yet implemented")
    def all(self):
        """TODO implement caching, this only does a few falsy things
        >>> a = SparseObjectArray(4, default=2); a.all()
        True
        >>> a[1:2] = 0; a.all()
        False
        """
        return all(self.runs.keys())
    def none(self):
        return not any(self.runs.keys())
    def index(self, value):
        """Return index of element or raise ValueError if not found
        >>> a = SparseObjectArray(4, default=2); a.index(2)
        0
        """
        try:
            return min(x[0] for x in self.runs[value])
        except IndexError:
            raise ValueError('%s is not in %s instance' % (value, self.__class__.__name__))

    def __getitem__(self, key):
        """Get a slice or the value of an entry

        >>> s = SparseObjectArray(6, default=0); s[2:4] = 2;
        >>> s, s.changes, s.values
        (SparseObjectArray([0, 0, 2, 2, 0, 0]), [0, 2, 4], [0, 2, 0])
        >>> s[1:5], s[1:5].changes
        SparseObjectArray([0, 2, 2, 0])

        #>>> s[0:5]
        #SparseObjectArray([0, 0, 2, 2, 0])
        #>>> s[1:6]
        #SparseObjectArray([0, 2, 2, 0, 0])
        #>>> s[2:6]
        #SparseObjectArray([2, 2, 0, 0])
        #>>> s = SparseObjectArray(6, default=0); s.changes = [0]; s.values = [0]; s.runs = {0:{(0, 6)}}
        #>>> s
        #SparseObjectArray([0, 0, 0, 0, 0, 0])
        #>>> s = SparseObjectArray(4, default=0)
        #>>> a = s[1:3]
        #>>> a.changes
        #[0]
        """
        print >> sys.stderr, '-*-*-*-*-'
        if isinstance(key, slice):
            start, end = self._decode_slice(key)
            print 'start:', start, 'end:', end
            before_or_at_start = bisect.bisect_right(self.changes, start) - 1
            before_or_at_end = bisect.bisect_right(self.changes, end) - 1
            result = SparseObjectArray(end - start)

            if self.changes[before_or_at_start] - start == 0:
                # then we're staring right on a run, we'll get it in a sec
                result.changes = []
                result.values = []
            else:
                result.changes = [0]
                result.values = [self.values[before_or_at_end]]

            #PLACEMARK TOM THOMAS BALLINGER I'M HERE
            # TODO fix this to use sensible logic, likely parallel with setitem
            result.changes.extend([change - start for change in self.changes[before_or_at_start+1:end_index]])
            result.values.extend(self.values[start_index-1:end_index])

            if self.changes[before_or_at_end] == end:
                pass
            else:
                result.changes.append(self.changes[before_or_at_end])
                result.values.append(self.values[before_or_at_end])


            result.runs = collections.defaultdict(set)
            temp = result.changes+[end-start]
            for i, value in enumerate(result.values):
                result.runs[value].add((result.changes[i], temp[i+1]))

            return result
        else:
            if key >= len(self):
                raise IndexError(key)

            index_of_value_at_or_before_pos = bisect.bisect_right(self.changes, key) - 1
            return self.values[index_of_value_at_or_before_pos]

    def __repr__(self):
        return 'SparseObjectArray('+repr([x for x in self])+')'
    def __setitem__(self, key, value):
        """Sets item or slice to an integer
        changes, values, runs
        [0], [0], {0:{(0, 100)}}
        s[5:10] = 2
        [0,5,10], [0, 2, 0], {0:{(0, 5), (10, 100)}, 2:{(5, 10)}}

        >>> s = SparseObjectArray(6, default=0); s
        SparseObjectArray([0, 0, 0, 0, 0, 0])
        >>> s.runs
        defaultdict(<type 'set'>, {0: set([(0, 6)])})
        >>> s[4:6] = 7; s.changes, s.values, s
        ([0, 4], [0, 7], SparseObjectArray([0, 0, 0, 0, 7, 7]))
        >>> s.runs
        defaultdict(<type 'set'>, {0: set([(0, 4)]), 7: set([(4, 6)])})
        >>> s[:1] = 3; s.changes, s.values, s
        ([0, 1, 4], [3, 0, 7], SparseObjectArray([3, 0, 0, 0, 7, 7]))
        >>> s.runs
        defaultdict(<type 'set'>, {0: set([(1, 4)]), 3: set([(0, 1)]), 7: set([(4, 6)])})
        >>> s[1:2] = 6; s.changes, s.values, s
        ([0, 1, 2, 4], [3, 6, 0, 7], SparseObjectArray([3, 6, 0, 0, 7, 7]))
        >>> s.runs
        defaultdict(<type 'set'>, {0: set([(2, 4)]), 3: set([(0, 1)]), 6: set([(1, 2)]), 7: set([(4, 6)])})
        >>> s[:] = 0; s.changes, s.values, s
        ([0], [0], SparseObjectArray([0, 0, 0, 0, 0, 0]))
        >>> s.runs
        defaultdict(<type 'set'>, {0: set([(0, 6)])})
        """
        #print >> sys.stderr, 'initial changes, values:', self.changes, self.values
        if isinstance(key, slice):
            start, end = self._decode_slice(key)
            before_or_at_start = bisect.bisect_right(self.changes, start) - 1
            before_or_at_end = bisect.bisect_right(self.changes, end) - 1
            #print >> sys.stderr, '\n\n\nchanges:', self.changes
            #print >> sys.stderr, 'values:', self.changes
            #print >> sys.stderr, 'start, end:', start, end
            #print >> sys.stderr, 'before_or_at_start_index, before_or_at_end_index:', before_or_at_start, before_or_at_end

            new_changes = self.changes[:before_or_at_start]
            new_values = self.values[:before_or_at_start]

            before_run = None
            new_run = [start, end]
            after_run = None

            if self.values[before_or_at_start] == value:
                new_changes.append(self.changes[before_or_at_start])
                new_values.append(self.changes[before_or_at_start])
                # replace before run, if finish actually extends it
                new_run[0] = self.changes[before_or_at_start]
            elif self.changes[before_or_at_start] == start:
                new_changes.append(start)
                new_values.append(value)
                # throw out the before run, then add new one
            elif self.changes[before_or_at_start] < start:
                new_changes.append(self.changes[before_or_at_start])
                new_values.append(self.values[before_or_at_start])
                new_changes.append(start)
                new_values.append(value)
                # shorten before run, then add new one
                before_run = [self.changes[before_or_at_start], start]
            else:
                raise Exception("Logic Error")

            if end == self.length:
                pass
                # extend run we're modifying
            elif self.values[before_or_at_end] == value:
                # extend run we're modifying through next run and remove after run
                new_run[1] = self.changes[before_or_at_end]
            elif self.changes[before_or_at_end] == end:
                new_changes.append(self.changes[before_or_at_end])
                new_values.append(self.values[before_or_at_end])
                # use our run, keep next run
                if len(self.changes) == before_or_at_end + 1:
                    after_run = [end, len(self)]
                else:
                    after_run = [end, self.changes[before_or_at_end+1]]
            elif self.changes[before_or_at_end] < end:
                new_changes.append(end)
                new_values.append(self.values[before_or_at_end])
                # add our run, shorten next run
                if len(self.changes) == before_or_at_end + 1:
                    after_run = [end, len(self)]
                else:
                    after_run = [end, self.changes[before_or_at_end + 1]]
            else:
                raise Exception("Logic Error")

            new_changes.extend(self.changes[before_or_at_end+1:])
            new_values.extend(self.values[before_or_at_end+1:])

            self.changes += [len(self)] # not how it's stored, but it's never accessed again for loop works better
            #print >> sys.stderr, 'initial runs:', self.runs
            for i in range(before_or_at_start, before_or_at_end+1):
                #print >> sys.stderr, 'trying to remove', (self.changes[i], self.changes[i+1]), 'from', self.values[i]
                self.runs[self.values[i]].remove((self.changes[i], self.changes[i+1]))
                if self.runs[self.values[i]] == set():
                    del self.runs[self.values[i]]
            #print >> sys.stderr, 'runs after removing:', self.runs, 'values', new_values, 'changes', new_changes, 'new run', new_run
            #print >> sys.stderr, 'before run:', before_run
            if before_run:
                self.runs[self.values[before_or_at_start]].add(tuple(before_run))
            #print >> sys.stderr, 'new run:', new_run
            self.runs[value].add(tuple(new_run))
            #print >> sys.stderr, 'after run:', after_run
            if after_run:
                self.runs[self.values[before_or_at_end]].add(tuple(after_run))
            #print >> sys.stderr, 'runs after adding:', self.runs, 'values', new_values, 'changes', new_changes, 'new run', new_run

            self.changes = new_changes
            self.values = new_values

        else:
            raise ValueError("Single element assignment not allowed")

class SparseBitArray(SparseArray):
    """Sparse BitArray, in which data is represented by indices of changes
    between runs of set and unset values

    >>> s = SparseBitArray(20); s
    SparseBitArray('00000000000000000000')
    >>> s = SparseBitArray(iterable=[1,0,0,1], scale=3, repetitions=2); s
    SparseBitArray('111000000111111000000111')
    >>> s[:] = True; all(s), any(s)
    (True, True)
    """
    def __init__(self, *args, **kwargs):
        super(SparseBitArray, self).__init__(*args, **kwargs)

    def _initialize_structures(self):
        self.changes = []
        self.cached_ones = None

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
        if x:
            return self.changes[0]
        else:
            if self.changes and self.changes[0] == 0:
                return self.changes[1]
            else:
                return 0
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

    def __repr__(self):
        s = ''.join(str(int(x)) for x in self)
        return 'SparseBitArray(\'%s\')' % s



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
        value = bool(value)
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
