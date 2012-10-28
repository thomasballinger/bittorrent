import time
import weakref
import socket
from torrent import ActiveTorrent
from reactor_select import Reactor
from peer import Peer

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
        return weakref.proxy(t)

    def move_to_torrent(self, peer, info_hash):
        for torrent in self.torrents:
            if torrent.info_hash == info_hash:
                torrent.peers.append(peer)
                peer.set_torrent(torrent)
                return True
        return False

