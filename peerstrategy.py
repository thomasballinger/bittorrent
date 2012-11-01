import logging
import msg
def keep_asking_strategy(peer):
    if not peer.interested:
        logging.info('%s sending interested', peer)
        peer.send_msg(msg.interested())
        peer.interested = True

    if not peer.choked:
        while len(peer.outstanding_requests) < 10:
            needed_piece = peer.torrent.get_needed_request()
            if needed_piece:
                logging.info('torrent needed_piece: %s', repr(needed_piece))
                peer.send_msg(needed_piece)
            else:
                break
    if peer.torrent.piece_checked.count(1) == len(peer.torrent.piece_hashes):
        for p in peer.torrent.peers:
            p.strategy = cancel_all_strategy

def cancel_all_strategy(peer):
    logging.info('file download complete')
    peer.strategy = do_nothing_strategy

def do_nothing_strategy(peer):
    pass

def wait_for_handshake_strategy(peer):
    """wait_for_handshake strategy is initially for peers not yet connected to a torrent"""
    if peer.handshake:
        logging.info('%s switching to do_nothing_strategy', peer)
        peer.strategy = do_nothing_strategy

