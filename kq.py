import select
from pprint import pformat
from collections import defaultdict

KQ_EVS = dict((getattr(select, att), att) for att in dir(select) if att.startswith('KQ_EV_'))
KQ_FILTERS = dict((getattr(select, att), att) for att in dir(select) if att.startswith('KQ_FILTER_'))
KQ_NOTE_NUMS = dict((att, getattr(select, att)) for att in dir(select) if att.startswith('KQ_NOTE_'))

KQ_NOTE_MAP = {
    'KQ_FILTER_READ' : [
        'KQ_NOTE_LOWAT',
        ],
    'KQ_FILTER_WRITE' : [
        'KQ_NOTE_LOWAT',
        ],
    'KQ_FILTER_VNODE' : [
        'KQ_NOTE_DELETE',
        'KQ_NOTE_WRITE',
        'KQ_NOTE_EXTEND',
        'KQ_NOTE_ATTRIB',
        'KQ_NOTE_LINK',
        'KQ_NOTE_RENAME',
        'KQ_NOTE_REVOKE',
    ],
    'KQ_FILTER_PROC' : [
        'KQ_NOTE_EXIT',
        'KQ_NOTE_FORK',
        'KQ_NOTE_EXEC',
        'KQ_NOTE_PCTRLMASK',
        'KQ_NOTE_PDATAMASK',
        'KQ_NOTE_TRACK',
        'KQ_NOTE_CHILD',
        'KQ_NOTE_TRACKERR',
    ],
}
#    'KQ_FILTER_NETDEV' : [
#        'KQ_NOTE_LINKUP',
#        'KQ_NOTE_LINKDOWN',
#        'KQ_NOTE_LINKINV',
#    ],
#}

for filter in KQ_NOTE_MAP:
    d = {}
    for note in KQ_NOTE_MAP[filter]:
        num = KQ_NOTE_NUMS[note]
        d[num] = note
    KQ_NOTE_MAP[filter] = d

def pformat_kevent(kevent):
    pretty_filter = KQ_FILTERS.get(kevent.filter, '?')
    pretty_flags = []
    for value in KQ_EVS:
        if value & kevent.flags:
            pretty_flags.append(KQ_EVS[value])
    pretty_fflags = []
    for value, fflag in KQ_NOTE_MAP[pretty_filter].iteritems():
        if value & kevent.fflags:
            pretty_fflags.append(fflag)
    return pformat({'ident':kevent.ident, 'filter':pretty_filter, 'flags':pretty_flags, 'filter flags':pretty_fflags})

# A kqueue wrapper.                                                                                                                                                                
class KQ(object):
    def __init__(self):
        self.kq = select.kqueue()
        self.active_kevents = defaultdict(dict)
        self.io_objects = {}

    def __str__(self):
        return 'KQ wrapper: '+pformat(self.active_kevents)

    def reg_read(self, fileobject): self.register(fileobject, select.KQ_FILTER_READ)
    def reg_write(self, fileobject): self.register(fileobject, select.KQ_FILTER_WRITE)
    def unreg_read(self, fileobject_or_fd): self.unregister(fileobject_or_fd, select.KQ_FILTER_READ)
    def unreg_write(self, fileobject_or_fd): self.unregister(fileobject_or_fd, select.KQ_FILTER_WRITE)

    def register(self, fileobject_or_fd, filter_):
        try:
            fd = int(fileobject_or_fd)
            fileobject = self.io_objects[fd]
        except TypeError:
            fileobject = fileobject_or_fd
            fd = fileobject.fileno()
        self.io_objects[fd] = fileobject
        ke = select.kevent(fd, filter_, select.KQ_EV_ADD)
        #print "The event we're sending:", pformat_kevent(ke)
        self.kq.control([ke], 0)
        self.active_kevents[fd][filter_] = ke

    def unregister(self, fileobject_or_fd, filter_):
        try:
            fd = int(fileobject_or_fd)
            fileobject = self.io_objects[fd]
        except TypeError:
            fileobject = fileobject_or_fd
            fd = fileobject.fileno()
        #print "Before unregister, these events were active for this fd: ", [pformat_kevent(self.active_kevents[fd][f]) for f in self.active_kevents[fd]]
        ke = select.kevent(fd, filter_, select.KQ_EV_DELETE)
        #print "The event we're sending:", pformat_kevent(ke)
        self.kq.control([ke], 0)

    def poll(self, timeout=None):
        events = self.kq.control(None, 1, timeout)
        return events

def interactive_test():
    kq = KQ()

    foo = open("foo")

    kq.register(foo, select.KQ_FILTER_WRITE)
    kq.register(foo, select.KQ_FILTER_READ)

    while True:
        r = raw_input("hit enter to poll, +/-r/w like +r to add/remove read/write")
        if len(r) == 2:
            if 'r' in r:
                filter_ = select.KQ_FILTER_READ
            elif 'w' in r:
                filter_ = select.KQ_FILTER_WRITE
            if '-' in r:
                kq.unregister(foo, filter_)
            elif '+' in r:
                kq.register(foo, filter_)
            else:
                print 'polling...'
        elif 'read' in r:
            print 'reading from foo:', foo.read(10)
        else:
            print 'polling...'

        events = kq.poll(1)
        if not events:
            print 'poll timed out!'
        for event in events:
            print pformat_kevent(event)
            if event.filter == select.KQ_FILTER_WRITE:
                print "fd", event.ident, "Ready to be written to!"
            elif event.filter == select.KQ_FILTER_READ:
                print "fd", event.ident, "Ready to be read!"
            else:
                print "Event of some other type for fd", event.ident

if __name__ == '__main__':
    interactive_test()
