import bencode
import urllib
import sha
import time
import socket
import struct
import datetime
import bitstring

class Torrent(object):
    class ParsingException(Exception): pass
    def __init__(self, filename):
        self.filename = filename
        self.initialize_from_torrent_file()
    def __str__(self):
        return '<Torrent Object at '+str(id(self))+'; contents: '+self.name+'>'
    def __repr__(self): return 'Torrent("'+self.filename+'")'

    def initialize_from_torrent_file(self):
        torrent_dict = bencode.bdecode(open(self.filename).read())
        self.creation_date = datetime.datetime.fromtimestamp(torrent_dict['creation date'])
        self.announce_url = torrent_dict['announce']
        self.created_by = torrent_dict.get('created by', None)
        self.encoding = torrent_dict.get('encoding', None)
        info_dict = torrent_dict['info']
        self.info_hash = sha.new(bencode.bencode(info_dict)).digest()
        self.piece_length = info_dict['piece length']
        self.piece_hashes = [info_dict['pieces'][i:i+20] for i in range(0, len(info_dict['pieces']), 20)]
        self.private = bool(info_dict.get('private', 0))
        if 'files' in info_dict:
            self.mode = 'multi-file'
            self.length = sum([f['length'] for f in info_dict['files']])
            self.name = '; '.join([f['path'][0] for f in info_dict['files']])
        else:
            self.mode = 'single-file'
            self.name = info_dict['name']
            self.length = info_dict['length']
        if self.length > len(self.piece_hashes) * self.piece_length:
            raise Torrent.ParsingException('File size is greater than total size of all pieces')

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
    def __init__(self):
        self.client_id = (str(time.time()) + 'tom client in Python that may not work correctly')[:20]
        self.port = 6881
        self.peers = []

    def announce(self, torrent):
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
        print 'opening', full_url, '...'
        response_data = bencode.bdecode(urllib.urlopen(full_url).read())

        peers_data = response_data['peers']
        peer_addresses = []
        for sixbits in [peers_data[i:i+6] for i in range(0,len(peers_data),6)]:
            peer_addresses.append(('.'.join(str(ord(ip_part)) for ip_part in sixbits[:4]), 256*ord(sixbits[4])+ord(sixbits[5])))

        #TODO fill out with our listening addr if we can figure it out
        our_ip = '127.0.0.1'
        peer_addresses = [x for x in peer_addresses if x[0] != our_ip or x[1] != self.port]
        response_data['peers'] = peer_addresses
        return response_data

    def add_peer(self, torrent, (ip, port)):
        peer = Peer(self, torrent, (ip, port))
        self.peers.append(peer)
        return peer

class Peer(object):
    """Represents a connection to a peer regarding a specific torrent"""
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
        self.connect()

    def parse_message(self):
        """If a full message exists on the buffer, pull it off and return it

        If incomplete message, returns 'incomplete message'
        If nothing on buffer, returns None
        """
        temp = ''.join(self.buffer)
        print 'current buffer length:', len(temp)
        print 'front end of buffer:', repr(temp[:50])
        if len(temp) == 0:
            return None
        elif len(temp) >= 49 and temp[1:20] == 'BitTorrent protocol':
            l = ord(temp[0])
            protocol = temp[1:20]
            reserved = temp[20:28]
            info_hash = temp[28:48]
            peer_id = temp[48:68]
            self.buffer = [temp[68:]]
            return ('handshake', protocol, reserved, info_hash, peer_id)
        elif len(temp) >= 4:
            length = struct.unpack('!I', temp[:4])[0]
            if len(temp) < length + 4:
                print 'returning "incomplete message"',
                print '(looks like a', msg_dict[ord(temp[4])], 'message)'
                return 'incomplete message'
            self.buffer = [temp[length+4:]]
            if length == 0:
                return ('keepalive',)
            msg_id = ord(temp[4])
            kind = msg_dict[msg_id]
            if kind == 'bitfield':
                return ('bitfield', bitstring.BitArray(bytes=temp[5:length+4]))
            elif kind == 'piece':
                index, begin = struct.unpack('!II', temp[5:13])
                return ('piece', index, begin, temp[13:length+4])
            elif kind == 'have':
                (index,) = struct.unpack('!I', temp[5:9])
                return ('have', index)
            else:
                return kind,
        else:
            print 'received unknown or incomplete message, or perhaps prev parse consumed too much:'
            print repr(temp)

    def connect(self):
        pstr = "BitTorrent protocol"
        pstrlen = len(pstr)
        reserved = '\x00'*8
        handshake = ''.join([chr(pstrlen), pstr, reserved, self.torrent.info_hash, self.client.client_id])
        assert len(handshake) == 49+19

        self.s = socket.socket()
        print 'connecting to', self.ip, 'on port', self.port, '...'
        self.s.connect((self.ip, self.port))
        def p(msg): print 'sending', len(msg), 'bytes:', repr(msg); self.s.send(msg)
        p(handshake)
        p(bitfield(self.torrent.bitfield))

        # to be replaced with state machine
        p(interested())
        p(request(0, 0, 2**14))
        print '---'

    def read_socket(self):
        data = self.s.recv(10000)
        self.buffer.append(data)
        print 'received ',len(data), 'bytes of data from remote peer', repr(data[:20]), '...'

    def get_message(self):
        while True:
            msg = self.parse_message()
            if msg is None:
                print 'nothing to read from buffer, so we\'re reading from socket'
                self.read_socket()
            elif msg == 'incomplete message':
                self.read_socket()
            else:
                break
        print 'parsed a message:', repr(msg)[:200]
        self.parsed_last_message = time.time()
        if msg[0] == 'handshake':
            self.handshook = True
        elif msg[0] == 'keepalive':
            pass
        elif msg[0] == 'bitfield':
            self.peer_bitfield = msg[1]
        elif msg[0] == 'unchoke':
            self.choked = False
        elif msg[0] == 'choke':
            self.choked = True
        elif msg[0] == 'interested':
            self.peer_interested = True
        elif msg[0] == 'not_interseted':
            self.peer_interested = False
        elif msg[0] == 'have':
            index = msg[1]
            print index
            self.peer_bitfield[index] = 1
            print 'know we know peer has piece'
        elif msg[0] == 'request':
            print 'doing nothing about peer request for peice'
        elif msg[0] == 'piece':
            _, index, begin, data = msg
            print 'receiving data'
            self.torrent.add_data(index, begin, data)
        else:
            print 'didn\'t correctly process', msg
            raise Exception('missed a message')
        return msg

msg_dict = {
        0 : 'choke',
        1 : 'unchoke',
        2 : 'interested',
        3 : 'not_interested',
        4 : 'have',
        5 : 'bitfield',
        6 : 'request',
        7 : 'piece',
        }

def keep_alive(): return '\x00' * 4
def choke(): return msg(0)
def unchoke(): return msg(1)
def interested(): return msg(2)
def not_interested(): return msg(3)
def have(piece_index): return msg(4, struct.pack('!I', piece_index)) #TODO zero-based index in what format?
def bitfield(bitfield): return msg(5, bitfield.tobytes())
def request(index, begin, length): return msg(6, struct.pack('!III', index, begin, length))
"""
def piece(index, begin, block)
def cancel(index, begin, length)
def port(listen_port)
"""
def msg(kind, *args):
    payload = ''.join(args)
    message_id = chr(kind)
    prefix = struct.pack('!I', len(message_id) + len(payload))
    return prefix + message_id + payload

def main():
    client = BittorrentClient()
    t = ActiveTorrent('/Users/tomb/Downloads/How To Speed Up Your BitTorrent Downloads [mininova].torrent')
    t = ActiveTorrent('/Users/tomb/Downloads/Probity - THE ELECTRONiC CONNECTiON 28 [Trance-House-Progressive] [mininova].torrent')
    #t = ActiveTorrent('/Users/tomb/Downloads/The best social Forex trading platform - follow the leaders and make a fortune [mininova].torrent')
    #t = ActiveTorrent('/Users/tomb/Desktop/test.torrent')
    print repr(t)
    announce_data = client.announce(t)
    print announce_data

    (ip, port) = (announce_data['peers'][0])
#(ip, port) = announce_data['peers'][-1]
    p = client.add_peer(t, (ip, port))
    while True:
        p.get_message()

def test():
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == '__main__':
    main()
