

encodings = {
        dict : lambda x: 'd'+''.join([bencode(str(k))+bencode(v) for k,v in sorted(x.items(), key=lambda kv: kv[0])])+'e',
        list : lambda x: 'l'+''.join([bencode(el) for el in x])+'e',
        str :  lambda x: str(len(x))+':'+x,
        int :  lambda x: 'i'+str(x)+'e'
        }

def bencode(x):
    """
    Doesn't reject invalid data structures very well
    >>> bencode({'e':3})
    'd1:ei3ee'
    >>> d = {'a': 1, 'b': [2,3,'asdf'], 'cdef': {'qwerty':4}}
    >>> bencode(d)
    'd1:ai1e1:bli2ei3e4:asdfe4:cdefd6:qwertyi4eee'
    """
    return encodings[type(x)](x)

def bdecode(s):
    """
    >>> bdecode('i3e')
    3
    >>> d = {'a': 1, 'b': [2,3,'asdf'], 'cdef': {'qwerty':4}}
    >>> new = bdecode(bencode(d))
    >>> d == new
    True
    """
#TODO makes this tons more elegant - all in terms of reduce?
    if not hasattr(s, 'next'):
        s = (c for c in s)

    def parse_str(first):
        nums = first
        for c in s:
            if c in '0123456789':
                nums += c
            elif c == ':':
                num = int(nums, 10)
                return ''.join(s.next() for _ in range(num))
    def parse_int(first):
        assert first == 'i'
        nums = ''
        for c in s:
            if c in '0123456789':
                nums += c
            elif c == 'e':
                return int(nums)
    def parse_dict(first):
        assert first == 'd'
        d = {}
        key = None
        for c in s:
            if c == 'e':
                return d
            x = decode(c)
            if key is None:
                key = x
            else:
                d[key] = x
                key = None
    def parse_list(first):
        assert first == 'l'
        l = []
        for c in s:
            if c == 'e':
                return l
            l.append(decode(c))

    decoders = {'d': parse_dict, 'l': parse_list, 'i': parse_int}
    for numeral in '0123456789':
        decoders[numeral] = parse_str

    def decode(c):
        return decoders[c](c)

    return decode(s.next())


import doctest
doctest.testmod()
