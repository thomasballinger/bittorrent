import bencode
import urllib
import time
import socket

import bitstring

import msg
from torrent import Torrent
from reactor_select import Reactor
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

        #todo store this stuff on disk
        self.data = bytearray(self.length)
        self.bitfield = bitstring.BitArray(len(self.piece_hashes))

        self.num_bytes_have = 0

        self.peers = []

    def load(self, filename):
        #TODO check hashes of all pieces
        self.have_data[:] = 2**(self.length)-1
        self.data[:] = open(filename, 'rb').read()
        self.num_bytes_have = self.have_data.count(1)
        assert self.num_bytes_have == self.length

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
        print 'file now %02.2f' % self.percent(), 'percent done'

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

    def assign_needed_piece(self):
        """Returns a block to be requested, and marks it as pending"""
        try:
            start = self.pending.find('0b0')[0]
        except IndexError:
            return False
        length = 2**14
        length = self.piece_length
        self.pending[start:(start+length)] = 2**length - 1
        index = start / self.piece_length
        begin = start % self.piece_length
        length = min(length, self.length - start)
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
        print 'set torrent called on', self
        self.client = None
        self.torrent = active_torrent
        self.reactor = self.torrent.client.reactor

        self.peer_interested = False
        self.interested = False
        self.choked = True
        self.peer_choked = False
        self.peer_bitfield = bitstring.BitArray(len(active_torrent.piece_hashes))
        print 'set torrent done being called on', self

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
        self.strategy = respond_strategy
        self.reactor.add_readerwriter(self.s.fileno(), self)
        self.reactor.reg_read(self.s)

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
            print repr(s)
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
            print 'received messages', messages
            print 'with leftover bytes:', repr(self.read_buffer)
            print 'starting with', repr(self.read_buffer[:60])
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
            self.handshake = m
        elif m.kind == 'keepalive':
            pass
        elif m.kind == 'bitfield':
            self.peer_bitfield = bitstring.BitArray(bytes=m.bitfield)
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
            print 'torrent:', self.torrent
            if self.torrent is None:
                raise Exception(repr(self)+' can\'t process request when no torrent associated yet')
            if self.peer_interested:
                data = self.torrent.get_data_if_have(m.index, m.begin, m.length)
                if data:
                    self.send_msg(msg.piece(m.index, m.begin, data))
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

def keep_asking_strategy(peer):
    while len(peer.outstanding_requests) < 15:
        needed_piece = peer.torrent.assign_needed_piece()
        if needed_piece:
            peer.send_msg(needed_piece)
        else:
            break
    if peer.torrent.num_bytes_have == peer.torrent.length:
        for p in peer.torrent.peers:
            p.strategy = cancel_all_strategy

def cancel_all_strategy(peer):
    peer.strategy = do_nothing_strategy

def do_nothing_strategy(peer):
    pass

def respond_strategy(peer):
    """Respond strategy is initially for peers not yet connected to a torrent"""
    print 'running respond strategy for', peer
    if len(peer.read_buffer) > 68:
        print 'dieing because more than 68 bytes in read buffer, after we should have tried to parse'
        peer.die()
    if peer.handshake:
        if not peer.client.move_to_torrent(peer, peer.handshake.info_hash):
            print 'dieing because client couldn\'t find matching torrent'
            peer.die()
            return
        print 'switching to do_nothing_strategy'
        peer.strategy = do_nothing_strategy
        peer.send_msg(msg.handshake(info_hash=peer.torrent.info_hash, peer_id=peer.torrent.client.client_id))
        peer.send_msg(msg.bitfield(peer.torrent.bitfield))
        peer.send_msg(msg.unchoke())

def main():
    client = BittorrentClient()
    torrent = client.add_torrent('localtest.torrent')
    torrent.tracker_update()

    print torrent.tracker_peer_addresses
    external_ip = torrent.get_external_addr()
    print 'removing', (external_ip, client.port)
    addresses = filter(lambda ipport:(external_ip, client.port) != ipport, torrent.tracker_peer_addresses)
    print addresses

    if not addresses:
        print 'no one else on tracker!'
        return
    peer = torrent.add_peer(*addresses[0])
    peer.connect()
    #peer = torrent.add_peer('', 8001)
    peer.send_msg(msg.interested())
    peer.strategy = keep_asking_strategy
    peer.run_strategy()
    while True:
        r = client.reactor.poll(1)
        if r is None:
            return

def test():
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == '__main__':
    main()
