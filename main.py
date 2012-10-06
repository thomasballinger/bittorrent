import bencode
import urllib
import sha
import time
import socket
import struct
import datetime
import bitstring

def get_our_addr_used(host):
    """Returns the ip address used on our side to contact host"""
    # doesn't work for localhost! Returns 192.168.0.16 instead of 127.0.0.1

    # see http://en.wikipedia.org/wiki/Discard_Protocol for why port 9
    # see http://stackoverflow.com/questions/7334349/
    # python-get-local-ip-address-used-to-send-ip-data-to-a-specific-remote-ip-addres
    # for discussion of problem
    client_ip = 'unknown'
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((host, 9))
    client_ip = s.getsockname()[0]
    s.close()
    print 'our ip:', client_ip
    return client_ip

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
        for k,v in torrent_dict.iteritems():
            if k != 'info':
                print k,':',v
        self.creation_date = datetime.datetime.fromtimestamp(torrent_dict['creation date'])
        self.announce_url = torrent_dict['announce']
        self.created_by = torrent_dict.get('created by', None)
        self.encoding = torrent_dict.get('encoding', None)
        info_dict = torrent_dict['info']
        self.info_hash = sha.new(bencode.bencode(info_dict)).digest()
        print info_dict.keys()
        self.piece_length = info_dict['piece length']
        self.piece_hashes = [info_dict['pieces'][i:i+20] for i in range(0, len(info_dict['pieces']), 20)]
        self.private = bool(info_dict.get('private', 0))
        print torrent_dict
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
        self.have_piece = [False] * len(self.piece_hashes)
        self.data = [None]*self.length
        self.bitfield = bitstring.BitArray(len(self.piece_hashes))

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

class Peer(object):
    """Represents a connection to a peer regarding a specific torrent"""
    def __init__(self, client, torrent, (ip, port)):
        self.ip = ip
        self.port = port
        self.torrent = torrent
        self.client = client
        self.buffer = []
        self.connect()

    def parse_message(self):
        """If a full message exists on the buffer, pull it off and return it"""
        temp = ''.join(self.buffer)
        print 'length of message we have to parse:', len(temp)
        print 'message', repr(temp)
        if len(temp) >= 49 and temp[1:20] == 'BitTorrent protocol':
            print 'received handshake!'
            l = temp[0]
            protocol = temp[1:20]
            reserved = temp[20:28]
            info_hash = temp[28:48]
            peer_id = temp[48:68]
            print 'length, protocol, reserved, info_hash, peer_id'
            print [l, protocol, reserved, info_hash, peer_id]
            self.buffer = [temp[68:]]
            return ('handshake', reserved, info_hash, peer_id)
        elif len(temp) >= 4:
            length = struct.unpack('!I', temp[:4])[0]
            if length == 0:
                return ('keepalive')
            print length
            if len(temp) < length + 4:
                return 'incomplete message'
            self.buffer = [temp[length+4:]]
            msg_id = ord(temp[4])
            print 'msg id:', msg_id
            kind = msg_dict[msg_id]
            print 'received', kind, 'message!'
            if kind == 'have':
                return ('have', temp[5])
            elif kind == 'bitfield':
                return ('bitfield', bitstring.BitArray(bytes=temp[5:length+4]))
            elif kind == 'request':
                index, begin = struct.unpack('!II', temp[5:13])
                return ('piece', index, begin, temp[13:length+4])
            return kind
        else:
            print 'received unknown or incomplete message:'
            print repr(temp)

    def connect(self):
        pstr = "BitTorrent protocol"
        pstrlen = len(pstr)
        reserved = '\x00'*8
        handshake = ''.join([chr(pstrlen), pstr, reserved, self.torrent.info_hash, self.client.client_id])
        assert len(handshake) == 49+19

        s = socket.socket()
        print 'connecting to', self.ip, 'on port', self.port, '...'
        s.connect((self.ip, self.port))
        def p(msg): print 'sending', len(msg), 'bytes:', repr(msg); s.send(msg)
        p(handshake)
        p(bitfield(self.torrent.bitfield))
        p(interested())
        p(request(0, 0, 2**14))
        print '---'
        while True:
            raw_input('hit enter to receive data and attempt to read off a message')
            s.settimeout(.2)
            try:
                data = s.recv(10000)
                self.buffer.append(data)
                print 'received from remote peer:', repr(data)
            except socket.timeout:
                pass
            msg = self.parse_message()
            print msg
            print '---'

msg_dict = {
        0 : 'choke',
        1 : 'unchoke',
        2 : 'interested',
        3 : 'not_intersted',
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

client = BittorrentClient()
#t = ActiveTorrent('/Users/tomb/Desktop/test.torrent')
#t = ActiveTorrent('/Users/tomb/Downloads/How To Speed Up Your BitTorrent Downloads [mininova].torrent')
#t = ActiveTorrent('/Users/tomb/Downloads/Video Tutorial - Learn HTML and CSS in 30 Minutes. Website from scratch no extra programs ne [mininova].torrent')
t = ActiveTorrent('/Users/tomb/Downloads/The best social Forex trading platform - follow the leaders and make a fortune [mininova].torrent')
#t = ActiveTorrent('/Users/tomb/Desktop/test.torrent')
print t, repr(t)
announce_data = client.announce(t)
print announce_data
import random
(ip, port) = random.choice(announce_data['peers'])
#(ip, port) = announce_data['peers'][-1]
client.add_peer(t, (ip, port))

if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

