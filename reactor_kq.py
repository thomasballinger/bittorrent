"""Reactor with kq

First, instantiate a reactor.

Next, register a file descriptor integer and corresponding
object with the reactor.

Then, register read or write on the integer (and therefore object)
in order to have that object called on that read or write event

Implement the read_event / write_event interface in that object

Unregister read or write if you don't want the notification to happen again
"""

import select

import kq

class Reactor(object):
    def __init__(self):
        self.KQ = kq.KQ()
        self.fd_map = {}
    def reg_read(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        self.KQ.reg_read(fd)
    def reg_write(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        self.KQ.reg_write(fd)
    def unreg_read(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        self.KQ.unreg_read(fd)
    def unreg_write(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        self.KQ.unreg_write(fd)
    def add_readerwriter(self, fd, readerwriter):
        self.fd_map[fd] = readerwriter
        print self.fd_map
    def poll(self):
        """Triggers one read or write event"""
        events = self.KQ.poll(0)
        if not events:
            return False
        for event in events:
            if event.filter == select.KQ_FILTER_READ:
                self.fd_map[event.ident].read_event()
            elif event.filter == select.KQ_FILTER_WRITE:
                self.fd_map[event.ident].write_event()
            else:
                raise Exception("Not the filter we were expecting for this event")
