"""Torrent file object, representing only data encoded in the torrent file

>>> t = Torrent('./example.torrent'); t
Torrent('./example.torrent')
>>> str(t) #doctest: +ELLIPSIS
'<Torrent Object at ...; contents: Distributed by Mininova.txt; TorrentFreak BitTorrent Speed Tips 101.pdf>'
"""
import datetime
import time
import sha
import bencode
import os
import urllib
import sys
import socket
import weakref
import shutil

import bitstring

from diskbytearray import MultiFileDiskArray
from sparsebitarray import SBA
import torrentstrategy
import peerstrategy

import msg
from peer import Peer

class Torrent(object):
    """Torrent file data

    >>> t = Torrent('/Users/tomb/Downloads/soulpurge - broken heart ep.torrent')
    >>> t.files
    """
    def __init__(self, filename):
        self.filename = filename
        self.initialize_from_torrent_file()
    def __str__(self):
        return '<Torrent Object at '+str(id(self))+'; contents: '+self.name+'>'
    def __repr__(self):
        return 'Torrent(\''+self.filename+'\')'

    class ParsingException(Exception): pass

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
            self.files = [os.path.join(*f['path']) for f in info_dict['files']]
            self.file_sizes = [f['length'] for f in info_dict['files']]
            self.length = sum([f['length'] for f in info_dict['files']])
            self.name = '; '.join([f['path'][-1] for f in info_dict['files']])
        else:
            self.mode = 'single-file'
            self.name = info_dict['name']
            self.length = info_dict['length']
            self.files = [self.name]
            self.file_sizes = [self.length]
        if self.length > len(self.piece_hashes) * self.piece_length:
            raise Torrent.ParsingException('File size is greater than total size of all pieces')

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
        self.written = bitstring.BitArray(self.length)
        self.outputfolder = 'outputfolder'
        if os.path.exists(self.outputfolder):
            shutil.rmtree(self.outputfolder)

        #todo store this stuff on disk
        #self.data = bytearray(self.length)

        self.data = MultiFileDiskArray(self.file_sizes, [os.path.join(self.outputfolder, f) for f in self.files])
        self.piece_checked = bitstring.BitArray(len(self.piece_hashes))
        self.bitfield = bitstring.BitArray(len(self.piece_hashes))
        self.last_tracker_update = 0

        self.num_bytes_have = 0

        self.peers = []
        self.peer_histories = {}

        # Placeholder strategy
        self.strategy = lambda x: False
        self.client.reactor.start_timer(1, self)

    def timer_event(self):
        self.run_strategy()
        self.client.reactor.start_timer(10, self)

    def run_strategy(self):
        #print self, 'running strategy', self.strategy.__name__
        self.strategy(self)

    def check_piece_hash(self, i):
        piece_hash = self.piece_hashes[i]
        if self.piece_checked[i]:
            return True
        start = i*self.piece_length
        end = min((i+1)*(self.piece_length), self.length)
        if all(self.have_data[start:end]):
            piece_hash = sha.new(self.data[start:end]).digest()
            if piece_hash == self.piece_hashes[i]:
                self.piece_checked[i] = True
                sys.stdout.write('hashing piece %d/%d                 \r' % (i+1, len(self.piece_hashes)))
                sys.stdout.flush()
                return True
            else:
                print 'hash check failed!'
                print 'throwing out piece', i
                print '(bytes', start,'up to', end, ')'
                print 'lookup:', self.piece_hashes[i]
                print 'calculated:', piece_hash
                self.have_data[start:end] = 0
                self.data[start:end] = '\x00'*(end-start)
                self.pending[start:end] = 0
                return False
        return False

    def check_piece_hashes(self):
        """Returns the number of piece hashes checked"""
        checked_out = 0
        for i in range(len(self.piece_hashes)):
            if self.check_piece_hash(i):
                checked_out += 1
        return checked_out

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
        self.tracker_min_interval = response_data.get('min interval', None)
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
        print self.announce_url
        if self.announce_url.count(':') == 2:
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
        #TODO store result of peer connect in self.peer_history - maybe use peer_id too or instead
        # this probably has to happen later, because p.connect is async
        # probably should do this in peer.die()
        return weakref.proxy(p)

    def kill_peer(self, peer):
        self.peers.remove(peer)

    def add_data(self, index, begin, block):
        self.have_data[index*self.piece_length+begin:index*self.piece_length+begin+len(block)] = 2**(len(block))-1
        self.data[index*self.piece_length+begin:index*self.piece_length+begin+len(block)] = block
        self.num_bytes_have = self.have_data.count(1)
        sys.stdout.write('file now %02.2f percent done\r' % self.percent())
        sys.stdout.flush()
        #TODO check piece hash on the piece we might have finished
        # peer.torrent.check_piece_hashes()
        # this version checks every piece, which is unnecessary

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
        suggested_length = 2**14
        if peer:
            pending_pieces = []
            available = peer.peer_bitarray & ~self.pending
            suggested_length = peer.preferred_request_length
        length = self.piece_length
        index = start / self.piece_length
        begin = start % self.piece_length
        # don't ask for more in a piece than there is
        # and cut the last piece short if necessary
        length = min(suggested_length, self.piece_length - begin, self.length - start)
        self.pending[start:(start+length)] = 2**length - 1
        return msg.request(index=index, begin=begin, length=length)

    def return_outstanding_request(self, m):
        print 'returning', repr(m)
        self.pending[m.begin:(m.begin+m.length)] = 0

def test():
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == '__main__':
    test()
