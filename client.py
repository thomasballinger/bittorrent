import time
import weakref
from torrent import ActiveTorrent
from reactor_select import Reactor
from peer import Peer
from network import AcceptingConnection

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
        self.connection = AcceptingConnection('', self.port, self.reactor, self)
        self.pending_connections = []

    def receive_incoming_connection(self, s, ip, port):
        print 'receiving incoming connection from', ip, port
        p = Peer((ip, port), client=self)
        p.respond(s)
        self.pending_connections.append(p)

    def kill_peer(self, peer):
        self.pending_connections.remove(peer)

    def add_torrent(self, filename):
        t = ActiveTorrent(filename, self)
        self.torrents.append(t)
        return weakref.proxy(t)

    def move_to_torrent(self, peer, info_hash):
        for torrent in self.torrents:
            if torrent.info_hash == info_hash:
                torrent.peers.append(peer)
                peer.set_torrent(torrent)
                return True
        return False

