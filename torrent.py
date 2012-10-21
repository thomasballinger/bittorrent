"""Torrent file object

>>> t = Torrent('./example.torrent'); t
Torrent('./example.torrent')
>>> str(t) #doctest: +ELLIPSIS
'<Torrent Object at ...; contents: Distributed by Mininova.txt; TorrentFreak BitTorrent Speed Tips 101.pdf>'
"""

import datetime
import sha
import bencode

class Torrent(object):
    """Torrent file data"""
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
            self.length = sum([f['length'] for f in info_dict['files']])
            self.name = '; '.join([f['path'][0] for f in info_dict['files']])
        else:
            self.mode = 'single-file'
            self.name = info_dict['name']
            self.length = info_dict['length']
        if self.length > len(self.piece_hashes) * self.piece_length:
            raise Torrent.ParsingException('File size is greater than total size of all pieces')

def test():
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

if __name__ == '__main__':
    test()
