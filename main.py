import bencode
import urllib
import time
import socket

import bitstring

import msg
from torrent import Torrent

class ActiveTorrent(Torrent):
    """Keeps track of what's been downloaded, stores data"""
    def __init__(self, filename):
        Torrent.__init__(self, filename)
        #todo use a more efficient way to store what portions of pieces we have
        self.have_data = bitstring.BitArray(self.length)

        #todo store this stuff on disk
        self.data = bytearray(self.length)
        self.bitfield = bitstring.BitArray(len(self.piece_hashes))

    def add_data(self, index, begin, data):
        self.have_data[index*self.piece_length+begin:index*self.piece_length+begin+len(data)] = 1
        self.data[index*self.piece_length+begin:index*self.piece_length+begin+len(data)] = data
        print 'data added'
        print 'file now', self.percent(), 'percent done'

    def percent(self):
        return int(self.have_data.count(1) * 1.0 / self.length * 100)
        self.have_data

class BittorrentClient(object):
    """
    >>> client = BittorrentClient()
    >>> t = ActiveTorrent('./example.torrent')
    >>> client.tracker_update(t)
    True

    """
    def __init__(self):
        self.client_id = (str(time.time()) + 'tom client in Python that may not work correctly')[:20]
        self.port = 6881
        self.peers = []
        self.time_since_tracker_update = None

    def tracker_update(self, torrent):
        """Returns data from Tracker specified in torrent"""
        announce_query_params = {
            'info_hash' : torrent.info_hash,
            'peer_id' : self.client_id,
            'port' : self.port,
            'uploaded' : 0,
            'downloaded' : 0,
            'left' : torrent.length,
            'compact' : 1, # sometimes optional
           #'no_peer_id' :  # ignored if compact enabled
            'event' : 'started',
            #'ip' : ip # optional
            #'numwant' : 50 # optional
            #'trackerid' : tracker id, if included before # optional
        }

        addr = torrent.announce_url
        full_url = addr + '?' + urllib.urlencode(announce_query_params)
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

    def populate_peers(self):
        for ip, port in self.tracker_peer_addresses:
            peer = Peer(self, self.torrent, (ip, port))
            self.peers.append(peer)
        return peer

class Peer(object):
    """Represents a connection to a peer regarding a specific torrent

    >>> class FakeTorrent(): piece_hashes = ['1','2','3']
    >>> p = Peer('fakeclient', FakeTorrent, ('123.123.123.123', 1234)); p
    <Peer 123.123.123.123:1234>

    """
    def __init__(self, client, torrent, (ip, port)):
        self.ip = ip
        self.port = port
        self.torrent = torrent
        self.client = client
        self.buffer = []
        self.peer_interested = False
        self.interested = False
        self.choked = True
        self.peer_choked = False
        self.peer_bitfield = bitstring.BitArray(len(torrent.piece_hashes))
        self.handshook = False
        self.parsed_last_message = time.time()

    def __repr__(self):
        return '<Peer {ip}:{port}>'.format(ip=self.ip, port=self.port)

    def connect(self):
        """Establishes TCP connection to peer and sends handshake and bitfield"""
        self.s = socket.socket()
        print 'connecting to', self.ip, 'on port', self.port, '...'
        self.s.connect((self.ip, self.port))
        def p(x): print 'sending', len(x), 'bytes:', repr(x); self.s.send(str(x))
        p(msg.handshake(info_hash=self.torrent.info_hash, peer_id=self.client.client_id))
        p(msg.bitfield(self.torrent.bitfield))

        # to be replaced with state machine
        p(msg.interested())
        p(msg.request(0, 0, 2**14))
        print '---'

    def read_socket(self):
        data = self.s.recv(10000)
        self.buffer.append(data)
        print 'received ',len(data), 'bytes of data from remote peer', repr(data[:20]), '...'

    def get_message(self):
        while True:
            message, rest = msg.parse_message(''.join(self.buffer))
            self.buffer = [rest]
            if message is None:
                print 'nothing to read from buffer, so we\'re reading from socket'
                self.read_socket()
            elif message == 'incomplete message':
                print 'incomplete message; total buffer length ', len(rest)
                self.read_socket()
            else:
                break
        print 'parsed a message:', repr(message)[:80]
        self.parsed_last_message = time.time()
        if message[0] == 'handshake':
            self.handshook = True
        elif message[0] == 'keepalive':
            pass
        elif message[0] == 'bitfield':
            self.peer_bitfield = message[1]
        elif message[0] == 'unchoke':
            self.choked = False
        elif message[0] == 'choke':
            self.choked = True
        elif message[0] == 'interested':
            self.peer_interested = True
        elif message[0] == 'not_interseted':
            self.peer_interested = False
        elif message[0] == 'have':
            index = message[1]
            print index
            self.peer_bitfield[index] = 1
            print 'know we know peer has piece'
        elif message[0] == 'request':
            print 'doing nothing about peer request for peice'
        elif message[0] == 'piece':
            _, index, begin, data = message
            print 'receiving data'
            self.torrent.add_data(index, begin, data)
        else:
            print 'didn\'t correctly process', message
            raise Exception('missed a message')
        return message

def main():
    client = BittorrentClient()
    t = ActiveTorrent('/Users/tomb/Downloads/How To Speed Up Your BitTorrent Downloads [mininova].torrent')
    client.tracker_update(t)
    client.populate_peers()
    peer = client.peers[3]
    peer.connect()
    while True:
        p.get_message()

def test():
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == '__main__':
    #main()
    test()
