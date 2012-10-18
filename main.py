import bencode
import urllib
import time
import socket

import bitstring

import msg
from torrent import Torrent
from reactor import Reactor

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

    def add_data(self, index, begin, data):
        self.have_data[index*self.piece_length+begin:index*self.piece_length+begin+len(data)] = 1
        self.data[index*self.piece_length+begin:index*self.piece_length+begin+len(data)] = data
        print 'data added'
        print 'file now', self.percent(), 'percent done'

    def percent(self):
        return int(self.have_data.count(1) * 1.0 / self.length * 100)
        self.have_data

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

        self.parsed_last_message = time.time()
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
        self.reactor.add_connection(self.s.fileno(), self)
        self.reactor.reg_write(self.s)
        self.reactor.reg_read(self.s)

    def write_event(self):
        """Action to take if socket comes up as ready to be written to"""
        while self.messages_to_send:
            self.write_buffer += str(self.messages_to_send.pop(0))
        if self.write_buffer:
            sent = self.s.send(self.write_buffer)
            print self, 'sent', sent, 'bytes'
            self.write_buffer = self.write_buffer[sent:]
        if not self.write_buffer:
            self.reactor.unreg_write(self.s)

    def read_event(self):
        """Action to take if socket comes up as ready be read from"""
        #TODO don't hardcode this number
        s = self.s.recv(1024*1024)
        if not s:
            self.die()
        buff = self.read_buffer + s
        print self, 'received', len(s), 'bytes'
        messages, self.read_buffer = msg.messages_and_rest(buff)
        if s:
            print 'received messages', messages
            print 'with leftover bytes:', [hex(ord(x)) for x in self.read_buffer]
            print 'starting with', self.read_buffer[:60]
            self.messages_to_process.extend(messages)

    def die(self):
        self.reactor.unreg_write(self.s)
        self.reactor.unreg_read(self.s)
        self.s.close()
        self.torrent.kill_peer(self)

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
    torrent = client.add_torrent('/Users/tomb/Downloads/How To Speed Up Your BitTorrent Downloads [mininova].torrent')
    torrent.tracker_update()
    peer = torrent.add_peer(*torrent.tracker_peer_addresses[9])
    #peer = torrent.add_peer('', 8001)
    peer.send_msg(msg.interested())
    peer.send_msg(msg.request(0, 0, 2**14))
    while True:
        import time
        time.sleep(.5)
        client.reactor.shuttle()

        # to be replaced with state machine

def test():
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == '__main__':
    main()
