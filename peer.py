import socket
import time

import bitstring

import msg
import peerstrategy
from network import MsgConnection

REQUEST_MSG_TIMEOUT = 120

class Peer(object):
    """Represents a connection to a peer regarding a specific torrent

    But can also be instantiated without a torrent until after handshake

    >>> class FakeTorrent(): piece_hashes = ['1','2','3']
    >>> p = Peer(('123.123.123.123', 1234), active_torrent=FakeTorrent); p
    <Peer 123.123.123.123:1234>
    """
    def __init__(self, (ip, port), active_torrent=None, client=None):
        self.ip = ip
        self.port = port
        self.connection = None

        self.handshake = None
        self.connected = False
        self.dead = False
        self.connection = None

        self.torrent = None
        #this might depend on the type of peer later
        self.preferred_request_length = 2**14
        self.strategy = lambda x: False

        if active_torrent is not None:
            self.client = None
            self.set_torrent(active_torrent)
        elif client is not None:
            self.client = client
            self.torrent = None
            self.reactor = client.reactor
        else:
            raise ValueError("Need either a torrent or a client")

        self.reactor.start_timer(1, self)

    def set_torrent(self, active_torrent):
        self.client = None
        self.torrent = active_torrent
        self.reactor = self.torrent.client.reactor

        self.outstanding_requests = {}
        self.peer_interested = False
        self.interested = False
        self.choked = True
        self.peer_choked = False
        self.peer_bitfield = bitstring.BitArray(len(active_torrent.piece_hashes))
        #self.peer_bitfield = bitstring.BitArray((len(active_torrent.piece_hashes)+7) / 8 * 8)

        #if we already have a connection, then we are responding to a peer connection
        if self.connection:
            self.send_msg(msg.handshake(info_hash=self.torrent.info_hash, peer_id=self.torrent.client.client_id))
            self.send_msg(msg.bitfield(self.torrent.bitfield))
        else:
            self.connection = MsgConnection(self.ip, self.port, self.reactor, self)
            self.send_msg(msg.handshake(info_hash=self.torrent.info_hash, peer_id=self.torrent.client.client_id))
            self.send_msg(msg.bitfield(self.torrent.bitfield))
            self.send_msg(msg.unchoke())

    def __repr__(self):
        if self.torrent:
            return '<Peer {ip}:{port} for {torrent}>'.format(ip=self.ip, port=self.port, torrent=self.torrent)
        elif self.client:
            return '<Peer {ip}:{port} of {client}>'.format(ip=self.ip, port=self.port, client=self.client)
        else:
            return '<Peer {ip}:{port}>'.format(ip=self.ip, port=self.port)

    def send_msg(self, *messages):
        for m in messages:
            if m.kind == 'request':
                self.outstanding_requests[m] = time.time()
        self.connection.send_msg(*messages)

    def respond(self, s):
        self.connection = MsgConnection(self.ip, self.port, self.reactor, self, s)
        self.strategy = peerstrategy.respond_strategy
        self.run_strategy()

    def timer_event(self):
        self.run_strategy()
        if not self.dead:
            self.reactor.start_timer(1, self)

    def die(self):
        if self.dead:
            print '... but was already dead/dieing'
            raise Exception("Double Death")
        self.dead = True
        self.connection.die()
        self.return_outstanding_requests()
        self.reactor.cancel_timers(self)
        if self.torrent is not None:
            self.torrent.kill_peer(self)
        else:
            self.client.kill_peer(self)

    def check_outstanding_requests(self):
        now = time.time()
        for m, t_sent in list(self.outstanding_requests.iteritems()):
            t = now - t_sent
            if t > REQUEST_MSG_TIMEOUT:
                #print 'canceling message which has been outstanding for over a minute:',
                print 'outstanding request!'
                print m.index, m.begin, m.length, time.time() - t_sent
                #self.send_msg(msg.cancel(m.index, m.begin, m.length))
                #self.torrent.return_outstanding_request(m)
                #del self.outstanding_requests[msg.request(m.index, m.begin, m.length)]

    def return_outstanding_requests(self):
        for m, t_sent in self.outstanding_requests.iteritems():
            self.torrent.return_outstanding_request(m)

    def run_strategy(self):
        #print self, 'running strategy', self.strategy.__name__
        if self.dead:
            raise Exception('run_strategy was called for ', self, 'despite being dead already')
        self.strategy(self)

    def recv_msg(self, m):
        """Returns number of messages left in messages_to_process afterwards

        big state machine-y thing
        """
        #print 'processing message', repr(m)
        if m.kind == 'handshake':
            if self.handshake:
                raise Exception('Received second handshake')
            self.handshake = m
            if not self.torrent:
                if not self.client.move_to_torrent(self, self.handshake.info_hash):
                    print 'dieing because client couldn\'t find matching torrent'
                    self.die()
                    return
            if m.peer_id == self.torrent.client.client_id:
                print 'dieing because connected to ourselves'
                self.die()
                return
        elif m.kind == 'keep_alive':
            pass
        elif m.kind == 'bitfield':
            old_bitfield = self.peer_bitfield
            temp = bitstring.BitArray(bytes=m.bitfield)
            self.peer_bitfield = temp[:len(self.torrent.piece_hashes)]
            assert len(old_bitfield) == len(self.peer_bitfield)
        elif m.kind == 'unchoke':
            self.choked = False
        elif m.kind == 'choke':
            self.choked = True
        elif m.kind == 'interested':
            self.peer_interested = True
        elif m.kind == 'not_interested':
            self.peer_interested = False
        elif m.kind == 'have':
            self.peer_bitfield[m.index] = 1
        elif m.kind == 'request':
            #TODO prove this won't happen when we don't yet have an associated torrent,
            # or throw a nice error
            if self.torrent is None:
                raise Exception(repr(self)+' can\'t process request when no torrent associated yet')
            if self.peer_interested:
                data = self.torrent.get_data_if_have(m.index, m.begin, m.length)
                if data:
                    m = msg.piece(m.index, m.begin, data)
                    #print 'sending', repr(m), 'to', self
                    self.send_msg(m)
                else:
                    print self, 'was just asked for piece it didn\'t have'
            else:
                print 'peer requesting piece despite not sending interested, so not sending it'
        elif m.kind == 'piece':
            try:
                del self.outstanding_requests[msg.request(m.index, m.begin, len(m.block))]
            except KeyError:
                print 'got a request back that we had canceled - oh well!'
            self.torrent.add_data(m.index, m.begin, m.block)
        else:
            print 'didn\'t correctly process', repr(m)
            raise Exception('missed a message: ')
        self.run_strategy()
        return m
