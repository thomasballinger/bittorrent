import reactor_kq
import reactor_select

class FileReaderWriter(object):
    def __init__(self, reactor):
        self.r = reactor
        self.f = open('/tmp/%d' % id(self), 'w')
    def read_event(self):
        print 'processing read event'
        self.r.unreg_read(self.f.fileno())
    def write_event(self):
        print 'processing write event'
        self.r.unreg_write(self.f.fileno())
import socket
class SocketReaderWriter(object):
    listen_addr = ('', 9876)
    listen = socket.socket()
    listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen.bind(listen_addr)
    listen.listen(5)
    def __init__(self, reactor):
        self.r = reactor
        self.s = socket.socket()
        self.s.connect(SocketReaderWriter.listen_addr)
    def read_event(self):
        print 'processing read event and unregistering'
        self.r.unreg_read(self.s.fileno())
    def write_event(self):
        print 'processing write event and unregistering'
        self.r.unreg_write(self.s.fileno())

def interactive_test(module):
    r = module.Reactor()
    f = FileReaderWriter(r)
    r.add_readerwriter(f.f.fileno(), f)
    r.reg_read(f.f.fileno())
    s = SocketReaderWriter(r)
    r.add_readerwriter(s.s.fileno(), s)
    r.reg_write(s.s.fileno())
    while True:
        raw_input('Hit enter to poll for events')
        r.poll()

if __name__ == '__main__':
    try:
        print 'testing select'
        interactive_test(reactor_select)
    except KeyboardInterrupt:
        print 'testing kq'
        interactive_test(reactor_kq)

