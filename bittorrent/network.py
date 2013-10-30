"""Trying to approximate what Twisted does"""
import time
import socket
import msg
import logging

WAIT_TO_CONNECT = 8
KEEP_ALIVE_TIME = 20

class AcceptingConnection(object):
    def __init__(self, ip, port, reactor, object):
        self.object = object
        self.ip = ip
        self.port = port
        self.sock = socket.socket()
        self.reactor = reactor

        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(False)
        self.sock.bind((self.ip, self.port))
        self.sock.listen(5)

        self.reactor.add_readerwriter(self.sock.fileno(), self)
        self.reactor.reg_read(self.sock.fileno())

    def read_event(self):
        s, (ip, port) = self.sock.accept()
        self.object.receive_incoming_connection(s, ip, port)

class MsgConnection(object):
    """Translation layer from msg objects to the tcp wire

    Sends and receives messages as msg objects
    If passed a socket in init, use it - else
    open a new one
    """
    def __init__(self, ip, port, reactor, object, sock=None):
        self.object = object
        self.ip = ip
        self.port = port
        self.reactor = reactor
        self.has_received_data = False
        self.messages_to_send = []
        self.write_buffer = ''
        self.read_buffer = ''
        #TODO don't use strings for buffers
        self.connect(sock=sock)

    def send_msg(self, *messages):
        assert isinstance(messages[0], msg.Msg)
        self.messages_to_send.extend(messages)
        self.reactor.reg_write(self.s)

    def die(self):
        self.reactor.unreg_write(self.s)
        self.reactor.unreg_read(self.s)
        self.reactor.cancel_timers(self)
        self.s.close()

    def connect(self, sock=None):
        """Establishes TCP connection to peer and sends handshake and bitfield"""
        if sock: # then we're responding to a peer
            self.s = sock
        else:
            self.s = socket.socket()
            logging.info('connecting to %s on port %d...', self.ip, self.port)
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
            self.send_msg(msg.KeepAlive())
        self.reactor.start_timer(KEEP_ALIVE_TIME / 2, self)

    def write_event(self):
        """Action to take if socket comes up as ready to be written to"""
        if not self.has_received_data:
            logging.info('%s has connected!', repr(self))
            self.has_received_data = True
        while self.messages_to_send:
            self.last_sent_data = time.time()
            m = self.messages_to_send.pop(0)
            logging.info('%s scheduling send of message %s', repr(self.object), repr(m))
            self.write_buffer += m
            logging.debug('which translates to %d bytes: %s', len(self.write_buffer), repr(self.write_buffer))
        if self.write_buffer:
            sent = self.s.send(self.write_buffer)
            logging.info('%s sent %d bytes', self, sent)
            self.write_buffer = self.write_buffer[sent:]
        if not self.write_buffer:
            self.reactor.unreg_write(self.s)

    def read_event(self):
        """Action to take if socket comes up as ready be read from"""
        #TODO don't hardcode this number
        try:
            s = self.s.recv(1024*1024)
        except socket.error:
            logging.info('%s dieing because connection refused', repr(self))
            self.object.die() # since reading nothing from a socket means closed
            return
        if not s:
            logging.info('%s dieing because received read event but nothing to read on socket', repr(self))
            self.object.die() # since reading nothing from a socket means closed
            return
        logging.debug('received data: %s', repr(s))
        self.last_received_data = time.time()
        buff = self.read_buffer + s
        logging.info('%s received %d bytes', self, len(buff))
        messages, self.read_buffer = msg.parse_messages(buff)
        logging.debug('received messages: %s', repr(messages))
        logging.debug('with leftover bytes: %s', repr(self.read_buffer))
        for m in messages:
            logging.info('%s received message: %s', repr(self.object), repr(m))
            self.object.recv_msg(m)
