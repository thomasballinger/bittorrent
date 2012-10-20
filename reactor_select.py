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
        """Triggers one read or write event"""
        if not any([self.wait_for_read, self.wait_for_write]):
            return False
        read_fds, write_fds, err_fds = select.select(self.wait_for_read, self.wait_for_write, [])
        if not any([read_fds, write_fds, err_fds]):
            return False
        for fd in read_fds:
            self.fd_map[fd].read_event()
        for fd in write_fds:
            self.fd_map[fd].write_event()

if __name__ == '__main__':
    r = Reactor()
    class FileReaderWriter(object):
        def __init__(self):
            self.f = open('/tmp/%d' % id(self), 'w')
        def read_event(self):
            print 'processing read event'
            r.unreg_read(self.f.fileno())
        def write_event(self):
            print 'processing write event'
            r.unreg_write(self.f.fileno())
    import socket
    class SocketReaderWriter(object):
        listen_addr = ('', 9876)
        listen = socket.socket()
        listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen.bind(listen_addr)
        listen.listen(5)
        def __init__(self):
            self.s = socket.socket()
            self.s.connect(SocketReaderWriter.listen_addr)
        def read_event(self):
            print 'processing read event and unregistering'
            r.unreg_read(self.s.fileno())
        def write_event(self):
            print 'processing write event and unregistering'
            r.unreg_write(self.s.fileno())
    f = FileReaderWriter()
    r.add_readerwriter(f.f.fileno(), f)
    r.reg_read(f.f.fileno())
    s = SocketReaderWriter()
    r.add_readerwriter(s.s.fileno(), s)
    r.reg_write(s.s.fileno())
    while True:
        raw_input('Hit enter to poll for events')
        r.poll()
