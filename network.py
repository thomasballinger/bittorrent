"""Trying to approximate what Twisted does"""
import time
import socket
import msg

WAIT_TO_CONNECT = 8
KEEP_ALIVE_TIME = 20
class MsgConnection(object):
    """Translation layer from msg objects to the tcp wire

    Sends and receives messages as msg objects
    """
    def __init__(self, ip, port, reactor, object):
        self.object = object
        self.ip = ip
        self.port = port
        self.reactor = reactor
        self.has_received_data = False
        self.messages_to_send = []
        self.write_buffer = ''
        self.read_buffer = ''
        #TODO don't use strings for buffers
        self.connect()

    def send_msg(self, *messages):
        assert isinstance(messages[0], msg.Msg)
        self.messages_to_send.extend(messages)
        self.reactor.reg_write(self.s)

    def die(self):
        self.reactor.unreg_write(self.s)
        self.reactor.unreg_read(self.s)
        self.reactor.cancel_timers(self)
        self.s.close()

    def connect(self):
        """Establishes TCP connection to peer and sends handshake and bitfield"""
        self.s = socket.socket()
        print 'connecting to', self.ip, 'on port', self.port, '...'
        self.s.setblocking(False)
        try:
            self.s.connect((self.ip, self.port))
        except socket.error:
            pass #TODO check that it's actually the right error
        self.connect_started = time.time()
        self.reactor.add_readerwriter(self.s.fileno(), self)
        self.reactor.reg_write(self.s)
        self.reactor.reg_read(self.s)
        self.reactor.start_timer(min(KEEP_ALIVE_TIME / 2, WAIT_TO_CONNECT), self)
        #TODO add check that we actually connect at some point

    def timer_event(self):
        if not self.has_received_data:
            if time.time() - self.connect_started > WAIT_TO_CONNECT:
                #TODO check this in a better way
                self.object.die() #TODO check this in a better place
            return
        now = time.time()
        if now - self.last_sent_data > KEEP_ALIVE_TIME / 2:
            self.send_msg(msg.keep_alive())
        self.reactor.start_timer(KEEP_ALIVE_TIME / 2, self)

    def write_event(self):
        """Action to take if socket comes up as ready to be written to"""
        if not self.has_received_data:
            print self, 'has connected!'
            self.object.connected = True
            self.has_received_data = True
        while self.messages_to_send:
            self.last_sent_data = time.time()
            self.write_buffer += str(self.messages_to_send.pop(0))
            #print 'what we\'re going to write:'
            #print repr(self.write_buffer)
            #print len(self.write_buffer)
        if self.write_buffer:
            sent = self.s.send(self.write_buffer)
            #print self, 'sent', sent, 'bytes'
            self.write_buffer = self.write_buffer[sent:]
        if not self.write_buffer:
            self.reactor.unreg_write(self.s)

    def read_event(self):
        """Action to take if socket comes up as ready be read from"""
        #TODO don't hardcode this number
        try:
            s = self.s.recv(1024*1024)
        except socket.error:
            print self, 'dieing because connection refused'
            self.object.die() # since reading nothing from a socket means closed
            return
        if not s:
            print self, 'dieing because received read event but nothing to read on socket'
            self.object.die() # since reading nothing from a socket means closed
            return
        self.last_received_data = time.time()
        buff = self.read_buffer + s
        #print self, 'received', len(s), 'bytes'
        messages, self.read_buffer = msg.messages_and_rest(buff)
        #print 'received messages', messages
        #print 'with leftover bytes:', repr(self.read_buffer)
        #print 'starting with', repr(self.read_buffer[:60])
        for m in messages:
            self.object.recv_msg(m)
