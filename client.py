import sys
import urllib
import time
import socket
import sha
import os

import bencode
import bitstring

import msg
import strategy
from torrent import Torrent
from reactor_select import Reactor
from diskbytearray import DiskArray
from sparsebitarray import SBA

class BittorrentClient(object):
    """
    >>> client = BittorrentClient()
    >>> t = ActiveTorrent('./example.torrent', client)
    >>> t.tracker_update()
    True

    """
    def __init__(self, listen_port=6881):
        self.client_id = (str(time.time()) + 'tom client in Python that may not work correctly')[:20]
        self.port = listen_port
        self.torrents = []
        self.reactor = Reactor()
        self.start_listen()

    def start_listen(self):
        self.listen_socket = socket.socket()
        self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_socket.setblocking(False)
        self.listen_socket.bind(('', self.port))
        self.listen_socket.listen(5)
        self.reactor.add_readerwriter(self.listen_socket.fileno(), self)
        self.reactor.reg_read(self.listen_socket.fileno())
        self.pending_connections = []

    def read_event(self):
        s, (ip, port) = self.listen_socket.accept()
        print 'receiving incoming connection from', ip, port
        p = Peer((ip, port), client=self)
        p.s = s
        p.respond()
        self.pending_connections.append(p)

    def kill_peer(self, peer):
        self.pending_connections.remove(peer)

    def add_torrent(self, filename):
        t = ActiveTorrent(filename, self)
        self.torrents.append(t)
        return t

    def move_to_torrent(self, peer, info_hash):
        for torrent in self.torrents:
            if torrent.info_hash == info_hash:
                torrent.peers.append(peer)
                peer.set_torrent(torrent)
                return True
        return False

class ActiveTorrent(Torrent):
    """Contains torrent data and peers

    self.data: access to the data from disk
    self.have_data: bool array access which describes if we data
    """
    def __init__(self, filename, client):
        Torrent.__init__(self, filename)
        self.client = client
        #todo use a more efficient way to store what portions of pieces we have
        self.have_data = bitstring.BitArray(self.length)
        self.pending = bitstring.BitArray(self.length)
        self.checked = bitstring.BitArray(self.length)
        self.written = bitstring.BitArray(self.length)
        self.outputfilename = 'outputfile.jpg'
        if os.path.exists(self.outputfilename):
            os.remove(self.outputfilename)

        #todo store this stuff on disk
        #self.data = bytearray(self.length)
        self.data = DiskArray(self.length, self.outputfilename)
        self.bitfield = bitstring.BitArray(len(self.piece_hashes))

        self.num_bytes_have = 0

        self.peers = []

    def check_piece_hashes(self):
        """Returns the number of piece hashes checked"""
        checked = 0
        failed = 0
        for i, piece_hash in enumerate(self.piece_hashes):
            if self.checked[i]:
                checked += 1
                continue
            start = i*self.piece_length
            end = min((i+1)*(self.piece_length), self.length)
            if all(self.have_data[start:end]):
                checked += 1
                piece_hash = sha.new(self.data[start:end]).digest()
                if piece_hash == self.piece_hashes[i]:
                    self.checked[i] = True
                    sys.stdout.write('hashing piece %d/%d                 \r' % (i+1, len(self.piece_hashes)))
                    sys.stdout.flush()
                else:
                    print 'hash check failed!'
                    print 'throwing out piece', i
                    print '(bytes', start,'up to', end, ')'
                    print 'lookup:', self.piece_hashes[i]
                    print 'calculated:', piece_hash
                    failed += 1
                    self.have_data[start:end] = 0
                    self.data[start:end] = '\x00'*(end-start)
                    self.pending[start:end] = 0
        return checked - failed

    def load(self, filename):
        #TODO check hashes of all pieces
        self.have_data[:] = 2**(self.length)-1
        self.data[:] = open(filename, 'rb').read()
        self.num_bytes_have = self.have_data.count(1)
        assert self.num_bytes_have == self.length
        assert self.check_piece_hashes() == len(self.piece_hashes)

    def tracker_update(self):
        """Returns data from Tracker specified in torrent"""

        announce_query_params = {
            'info_hash' : self.info_hash,
            'peer_id' : self.client.client_id,
            'port' : self.client.port,
            'uploaded' : 0,
            'downloaded' : 0,
            'left' : self.length,
            'compact' : 1, # sometimes optional
           #'no_peer_id' :  # ignored if compact enabled
            'event' : 'started',
            #'ip' : ip # optional
            #'numwant' : 50 # optional
            #'trackerid' : tracker id, if included before # optional
        }

        addr = self.announce_url
        full_url = addr + '?' + urllib.urlencode(announce_query_params)
        print 'making request to', full_url
        response_data = bencode.bdecode(urllib.urlopen(full_url).read())

        self.last_tracker_update = time.time()
        self.tracker_min_interval = response_data['min interval']
        self.tracker_interval = response_data['interval']
        self.tracker_complete = response_data['complete']
        self.tracker_incomplete = response_data['incomplete']

        peers_data = response_data['peers']
        peer_addresses = []
        for sixbits in [peers_data[i:i+6] for i in range(0,len(peers_data),6)]:
            peer_addresses.append(
                    ('.'.join(str(ord(ip_part)) for ip_part in sixbits[:4]), 256*ord(sixbits[4])+ord(sixbits[5])))
        self.tracker_peer_addresses = tuple(peer_addresses)
        return True

    def get_external_addr(self):
        s = socket.socket()
        port = 80
        addr = self.announce_url
        if ':' in self.announce_url:
            _, first, rest = self.announce_url.split(':')
            addr = first.split('/')[-1]
            port = rest.split('/')[0]
            port = int(port)
        s.connect((addr, port))
        ip, port = s.getsockname()
        s.close()
        return ip

    def add_peer(self, ip, port):
        p = Peer((ip, port), active_torrent=self)
        self.peers.append(p)
        return p

    def kill_peer(self, peer):
        self.peers.remove(peer)

    def add_data(self, index, begin, block):
        self.have_data[index*self.piece_length+begin:index*self.piece_length+begin+len(block)] = 2**(len(block))-1
        self.data[index*self.piece_length+begin:index*self.piece_length+begin+len(block)] = block
        self.num_bytes_have = self.have_data.count(1)
        sys.stdout.write('file now %02.2f percent done\r' % self.percent())
        sys.stdout.flush()

    def get_data_if_have(self, index, begin, length):
        start = index*self.piece_length
        end = index*self.piece_length+length
        if all(self.have_data[start:end]):
            return str(self.data[start:end])
        else:
            return False

    def done(self):
        return self.num_bytes_have == self.length

    def percent(self):
        return self.num_bytes_have * 1.0 / self.length * 100

    def availability(self):
        """how many copies of the full file are available from connected peers"""
        raise Exception("Not Yet Implemented")

    def assign_needed_piece(self, peer=None):
        """Returns a block to be requested, and marks it as pending

        if a peer is provided, return a piece that we need that the peer has
        """
        try:
            start = self.pending.find('0b0')[0]
        except IndexError:
            return False
        if peer:
            pending_pieces = []
            available = peer.peer_bitarray & ~self.pending
        suggested_length = 2**14
        length = self.piece_length
        self.pending[start:(start+length)] = 2**length - 1
        index = start / self.piece_length
        begin = start % self.piece_length
        length = min(suggested_length, self.piece_length - start % self.piece_length)
        return msg.request(index=index, begin=begin, length=length)

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

        self.sent_handshake = False
        self.handshake = False
        self.connected = False
        self.dead = False

        self.last_received_data = time.time()
        self.last_sent_data = time.time()
        #TODO don't use strings for buffers
        self.read_buffer = ''
        self.write_buffer = ''
        self.messages_to_process = []
        self.messages_to_send = []
        self.outstanding_requests = {}
        self.torrent = None

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

        self.peer_interested = False
        self.interested = False
        self.choked = True
        self.peer_choked = False
        self.peer_bitfield = bitstring.BitArray(len(active_torrent.piece_hashes))
        #self.peer_bitfield = bitstring.BitArray((len(active_torrent.piece_hashes)+7) / 8 * 8)

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
                self.outstanding_requests[(m.index, m.begin)] = time.time()
        self.messages_to_send.extend(messages)
        #print 'message queue now looks like:', self.messages_to_send
        self.reactor.reg_write(self.s)

    def respond(self):
        self.strategy = strategy.respond_strategy
        self.reactor.add_readerwriter(self.s.fileno(), self)
        self.reactor.reg_read(self.s)
        self.run_strategy()

    def connect(self):
        """Establishes TCP connection to peer and sends handshake and bitfield"""
        self.s = socket.socket()
        print 'connecting to', self.ip, 'on port', self.port, '...'
        self.s.setblocking(False)
        try:
            self.s.connect((self.ip, self.port))
        except socket.error:
            pass #TODO check that it's actually the right error
        self.send_msg(msg.handshake(info_hash=self.torrent.info_hash, peer_id=self.torrent.client.client_id))
        self.send_msg(msg.bitfield(self.torrent.bitfield))
        self.reactor.add_readerwriter(self.s.fileno(), self)
        self.reactor.reg_write(self.s)
        self.reactor.reg_read(self.s)

    def write_event(self):
        """Action to take if socket comes up as ready to be written to"""
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
            self.die() # since reading nothing from a socket means closed
            return
        if not s:
            print self, 'dieing because received read event but nothing to read on socket'
            self.die() # since reading nothing from a socket means closed
            return
        self.last_received_data = time.time()
        buff = self.read_buffer + s
        #print self, 'received', len(s), 'bytes'
        messages, self.read_buffer = msg.messages_and_rest(buff)
        if s:
            #print 'received messages', messages
            #print 'with leftover bytes:', repr(self.read_buffer)
            #print 'starting with', repr(self.read_buffer[:60])
            self.messages_to_process.extend(messages)
            if self.process_all_messages():
                self.run_strategy()

    def timer_event(self):
        self.reactor.start_timer(1, self)
        self.run_strategy()

    def die(self):
        if self.dead:
            print '... but was already dead/dieing'
            raise Exception("Double Death")
        self.dead = True
        self.reactor.unreg_write(self.s)
        self.reactor.unreg_read(self.s)
        self.reactor.cancel_timers(self)
        self.s.close()
        if self.torrent is not None:
            self.torrent.kill_peer(self)
        else:
            self.client.kill_peer(self)

    def check_outstanding_requests(self):
        for (index, begin), t_sent in self.outstanding_requests.iteritems():
            print 'pending requests:', index, begin, time.time() - t_sent

    def run_strategy(self):
        #print 'running strategy', self.strategy.__name__
        self.strategy(self)

    def process_all_messages(self):
        if not self.messages_to_process:
            return False
        while self.messages_to_process:
            self.process_msg()

    def process_msg(self):
        """Returns number of messages left in messages_to_process afterwards

        big state machine-y thing
        """
        if not self.messages_to_process:
            return 0
        m = self.messages_to_process.pop(0)
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
        elif m.kind == 'keepalive':
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
            #print 'know we know peer has piece', m.index
        elif m.kind == 'request':
            #TODO prove this won't happen when we don't yet have an associated torrent,
            # or throw a nice error
            if self.torrent is None:
                raise Exception(repr(self)+' can\'t process request when no torrent associated yet')
            if self.peer_interested:
                data = self.torrent.get_data_if_have(m.index, m.begin, m.length)
                if data:
                    m = msg.piece(m.index, m.begin, data)
                    print 'sending', m, 'to', self
                    self.send_msg(m)
                else:
                    print self, 'was just asked for piece it didn\'t have'
            else:
                print 'peer requesting piece despite not sending interested, so not sending it'
        elif m.kind == 'piece':
            #print 'receiving data'
            del self.outstanding_requests[(m.index, m.begin)]
            self.torrent.add_data(m.index, m.begin, m.block)
        else:
            print 'didn\'t correctly process', repr(m)
            raise Exception('missed a message')
        return m

