"""Reactor with socket.select"""
"""
Notes on how nonblocking sockets work in Python
error on recv when nothing to read
error on write when write buffer is full
'' on recv if socket closed on other end
broken pipe error on write if receiver closes early
"""
import select

SOCKET_READ_AMOUNT = 1024*1024

class Reactor(object):
    def __init__(self):
        self.fd_map = {}
    def reg_read(self, fd):
        self.KQ.reg_read(fd)
    def reg_write(self, fd):
        self.KQ.reg_write(fd)
    def unreg_read(self, fd):
        self.KQ.unreg_read(fd)
    def unreg_write(self, fd):
        self.KQ.unreg_write(fd)
    def add_connection(self, fd, readerwriter):
        self.fd_map[fd] = readerwriter
    def shuttle(self):
        """Triggers one read or write event"""
        events = self.KQ.poll(0)
        if not events:
            return False
        event = events[0]
        print self.fd_map
        print event
        print event.ident
        if event.filter == select.KQ_FILTER_READ:
            self.fd_map[event.ident].read_event()
        elif event.filter == select.KQ_FILTER_WRITE:
            self.fd_map[event.ident].write_event()
        else:
            raise Exception("Not the filter we were expecting for this event")
