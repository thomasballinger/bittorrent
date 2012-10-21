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
    def __init__(self):
        self.client_id = (str(time.time()) + 'tom client in Python that may not work correctly')[:20]
        self.port = 6881
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
        print 'receiving incoming connection!'
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

    def add_peer(self, ip, port):
        p = Peer((ip, port), active_torrent=self)
        self.peers.append(p)
        return p

    def add_data(self, index, begin, block):
        self.have_data[index*self.piece_length+begin:index*self.piece_length+begin+len(block)] = 2**(len(block))-1
        self.data[index*self.piece_length+begin:index*self.piece_length+begin+len(block)] = block
        self.num_bytes_have = self.have_data.count(1)
        print 'file now %02.2f' % self.percent(), 'percent done'

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

        if active_torrent is not None:
            self.client = None
            self.set_torrent(active_torrent)
        elif client is not None:
            self.client = client
            self.torrent = None
            self.reactor = client.reactor

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

    def __repr__(self):
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
        s = self.s.recv(1024*1024)
        if not s:
            self.die() # since reading nothing from a socket means closed
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
        print self, 'is dieing'
        if self.dead:
            print '... but was already dead/dieing'
            return
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
            pass #print 'doing nothing about peer request for piece'
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
    if len(peer.read_buffer) > 68:
        peer.die()
    if peer.handshake:
        if not peer.client.move_to_torrent(peer, peer.handshake.info_hash):
            peer.die()
        peer.strategy = do_nothing_strategy
        peer.send_msg(msg.handshake(info_hash=peer.torrent.info_hash, peer_id=peer.torrent.client.client_id))
        peer.send_msg(msg.bitfield(peer.torrent.bitfield))
    #TODO I'm concerned that I may try to unregister an unregistered
    # event; peer.die() comes before any reg_write
    # For now all unregs return whether there was one there to
    # remove or not

def main():
    client = BittorrentClient()
    torrent = client.add_torrent('/Users/tomb/Desktop/test.torrent')
    torrent.tracker_update()
    peer = torrent.add_peer(*torrent.tracker_peer_addresses[1])
    peer.connect()
    #peer = torrent.add_peer('', 8001)
    peer.send_msg(msg.interested())
    peer.strategy = keep_asking_strategy
    peer.run_strategy()
    while True:
        client.reactor.poll()


def test():
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == '__main__':
    main()
