"""Reactor with socket.select

First, instantiate a reactor.

Next, register a file descriptor integer and corresponding
object with the reactor.

Then, register read or write on the integer (and therefore object)
in order to have that object called on that read or write event

Implement the read_event / write_event interface in that object

Unregister read or write if you don't want the notification to happen again
"""

import select

class Reactor(object):
    def __init__(self):
        self.fd_map = {}
        self.wait_for_read = set()
        self.wait_for_write = set()
    def reg_read(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        self.wait_for_read.add(fd)
    def reg_write(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        self.wait_for_write.add(fd)
    def unreg_read(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        self.wait_for_read.remove(fd)
    def unreg_write(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        self.wait_for_write.remove(fd)
    def add_readerwriter(self, fd, readerwriter):
        self.fd_map[fd] = readerwriter
    def poll(self):
        """Triggers every read or write event that is up"""
        if not any([self.wait_for_read, self.wait_for_write]):
            return False
        read_fds, write_fds, err_fds = select.select(self.wait_for_read, self.wait_for_write, [])
        if not any([read_fds, write_fds, err_fds]):
            return False
        for fd in read_fds:
            self.fd_map[fd].read_event()
        for fd in write_fds:
            self.fd_map[fd].write_event()
