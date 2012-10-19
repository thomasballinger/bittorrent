"""Reactor with socket.select

when a socket comes up, call its corresponding
readerwriter with .read_event() or .write_event()
"""
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
        self.wait_for_read = set()
        self.wait_for_write = set()
    def reg_read(self, fd):
        self.wait_for_read.add(fd)
    def reg_write(self, fd):
        self.wait_for_write.add(fd)
    def unreg_read(self, fd):
        self.wait_for_read.remove(fd)
    def unreg_write(self, fd):
        self.wait_for_write.remove(fd)
    def add_readerwriter(self, fd, readerwriter):
        self.fd_map[fd] = readerwriter
    def poll(self):
        """Triggers one read or write event"""
        print (self.wait_for_read, self.wait_for_write)
        read_fds, write_fds, err_fds = select.select(self.wait_for_read, self.wait_for_write, [])
        if not any([read_fds, write_fds, err_fds]):
            return False
        for fd in read_fds:
            print 'calling read_event for fd', fd
            self.fd_map[fd].read_event()
        if not read_fds:
            print 'no read fds'
        for fd in write_fds:
            print 'calling write_event for fd', fd
            self.fd_map[fd].write_event()
        if not write_fds:
            print 'no write fds'

if __name__ == '__main__':
    class FileReaderWriter(object):
        def __init__(self):
            self.f = open('/tmp/%d' % id(self), 'w')
        def read_event(self):
            print 'processing read event'
        def write_event(self):
            print 'processing write event'
    r = Reactor()
    f = FileReaderWriter()
    r.add_readerwriter(f.f.fileno(), f)
    r.reg_read(f.f.fileno())
    while True:
        raw_input('Hit enter to poll for events')
        r.poll()
