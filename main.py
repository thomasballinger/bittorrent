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

    def add_torrent(self, filename):
        t = ActiveTorrent(filename, self)
        self.torrents.append(t)
        return t

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
        p = Peer(self, (ip, port))
        self.peers.append(p)
        return p

    def get_pieces(self):
        pass

    def add_data(self, index, begin, block):
        self.have_data[index*self.piece_length+begin:index*self.piece_length+begin+len(block)] = 2**(len(block))-1
        self.data[index*self.piece_length+begin:index*self.piece_length+begin+len(block)] = block
        print 'file now %02.2f' % self.percent(), 'percent done'

    def percent(self):
        return self.have_data.count(1) * 1.0 / self.length * 100

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

    >>> class FakeTorrent(): piece_hashes = ['1','2','3']
    >>> p = Peer('fakeclient', FakeTorrent, ('123.123.123.123', 1234)); p
    <Peer 123.123.123.123:1234>
    """
    def __init__(self, active_torrent, (ip, port)):
        self.ip = ip
        self.port = port
        self.torrent = active_torrent
        self.reactor = active_torrent.client.reactor

        self.peer_interested = False
        self.interested = False
        self.choked = True
        self.peer_choked = False
        self.peer_bitfield = bitstring.BitArray(len(active_torrent.piece_hashes))

        self.sent_handshake = False
        self.received_handshake = False
        self.connected = False

        self.last_received_data = time.time()
        #TODO don't use strings for buffers
        self.read_buffer = ''
        self.write_buffer = ''
        self.messages_to_process = []
        self.messages_to_send = []
        self.connect()

    def __repr__(self):
        return '<Peer {ip}:{port}>'.format(ip=self.ip, port=self.port)

    def send_msg(self, *messages):
        self.messages_to_send.extend(messages)
        #print 'message queue now looks like:', self.messages_to_send
        self.reactor.reg_write(self.s)

    def connect(self):
        """Establishes TCP connection to peer and sends handshake and bitfield"""
        self.s = socket.socket()
        self.reactor
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
            self.process_all_messages()

    def die(self):
        self.reactor.unreg_write(self.s)
        self.reactor.unreg_read(self.s)
        self.s.close()
        self.torrent.kill_peer(self)

    def process_all_messages(self):
        while self.messages_to_process:
            self.process_msg()

    def process_msg(self):
        """Returns number of messages left in messages_to_process afterwards

        big state machine-y thing
        """
        if not self.messages_to_process:
            return 0
        m = self.messages_to_process.pop(0)
        print 'processing message', repr(m)
        if m.kind == 'handshake':
            self.handshook = True
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
            self.torrent.add_data(m.index, m.begin, m.block)
            new_m = self.torrent.assign_needed_piece()
            if new_m:
                self.send_msg(new_m)
        else:
            print 'didn\'t correctly process', repr(m)
            raise Exception('missed a message')
        return m

def main():
    client = BittorrentClient()
    #torrent = client.add_torrent('/Users/tomb/Downloads/How To Speed Up Your BitTorrent Downloads [mininova].torrent')
    torrent = client.add_torrent('/Users/tomb/Desktop/test.torrent')
    torrent.tracker_update()
    peer = torrent.add_peer(*torrent.tracker_peer_addresses[1])
    #peer = torrent.add_peer('', 8001)
    peer.send_msg(msg.interested())
    #peer.send_msg(msg.request(0, 0, 2**14))
    peer.send_msg(torrent.assign_needed_piece())
    peer.send_msg(torrent.assign_needed_piece())
    peer.send_msg(torrent.assign_needed_piece())
    peer.send_msg(torrent.assign_needed_piece())
    peer.send_msg(torrent.assign_needed_piece())
    peer.send_msg(torrent.assign_needed_piece())
    peer.send_msg(torrent.assign_needed_piece())
    peer.send_msg(torrent.assign_needed_piece())
    peer.send_msg(torrent.assign_needed_piece())
    peer.send_msg(torrent.assign_needed_piece())
    peer.send_msg(torrent.assign_needed_piece())
    peer.send_msg(torrent.assign_needed_piece())
    peer.send_msg(torrent.assign_needed_piece())
    while True:
        client.reactor.poll()

        # to be replaced with state machine

def test():
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == '__main__':
    main()
