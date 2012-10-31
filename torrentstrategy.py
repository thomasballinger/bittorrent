import time
import logging

import peerstrategy


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
                    addr = torrent.tracker_peer_addresses[self.addr_index]
                    logging.info('creating peer for %s', repr(addr))
                    peer = torrent.add_peer(*addr)
                    peer.strategy = peerstrategy.keep_asking_strategy
                    self.addr_index += 1
    __name__ = property(get_name)
