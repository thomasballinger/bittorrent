import time
import sys
import logging

from . import peerstrategy


class connect_and_ask_n_peers(object):
    def __init__(self, max_simul_peers):
        self.addr_index = 0
        self.max_simul_peers = max_simul_peers
    def get_name(self):
        return 'connect_and_ask_%d_peers' % self.max_simul_peers
    def __call__(self, torrent):
        torrent.check_piece_hashes()
        if time.time() - torrent.last_tracker_update > 600:
            torrent.tracker_update()

            addresses = torrent.tracker_peer_addresses

            logging.info( 'got these peers from tracker: %s', repr(torrent.tracker_peer_addresses))
            external_ip = torrent.get_external_addr()
            logging.info( 'removing %s:%d if it appears because it looks like it\'s us', external_ip, torrent.client.port)
            addresses = filter(lambda ipport:(external_ip, torrent.client.port) != ipport, torrent.tracker_peer_addresses)
            logging.info( 'so just using %s', repr(addresses))

            if not addresses:
                logging.warning( 'no one else on tracker!')
                return
            else:
                while len(torrent.peers) < self.max_simul_peers and self.addr_index < len(addresses):
                    addr = addresses[self.addr_index]
                    logging.info('creating peer for %s', repr(addr))
                    peer = torrent.add_peer(*addr)
                    peer.strategy = peerstrategy.keep_asking_strategy
                    self.addr_index += 1
    __name__ = property(get_name)

class quit_when_done(connect_and_ask_n_peers):
    def __call__(self, torrent):
        pieces_hashed = torrent.check_piece_hashes()
        if pieces_hashed == len(torrent.piece_hashes):
            sys.exit(0)
        connect_and_ask_n_peers.__call__(self, torrent)
    die_on_finish = True

