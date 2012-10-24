import time
KEEP_ALIVE_TIME = 30
import msg
def keep_asking_strategy(peer):
    peer.torrent.check_piece_hashes()
    peer.torrent.write_checked_pieces()
    while len(peer.outstanding_requests) < 15:
        needed_piece = peer.torrent.assign_needed_piece()
        if needed_piece:
            peer.send_msg(needed_piece)
        else:
            break
    #if peer.torrent.num_bytes_have == peer.torrent.length:
    if peer.torrent.checked == len(peer.torrent.piece_hashes):
        for p in peer.torrent.peers:
            p.strategy = cancel_all_strategy
    now = time.time()
    if now - peer.last_sent_data > KEEP_ALIVE_TIME:
        peer.send_msg(msg.keepalive())

def cancel_all_strategy(peer):
    print 'file download complete'
    peer.strategy = do_nothing_strategy

def do_nothing_strategy(peer):
    pass

def respond_strategy(peer):
    """Respond strategy is initially for peers not yet connected to a torrent"""
    print 'running respond strategy for', peer
    if len(peer.read_buffer) > 68:
        print 'dieing because more than 68 bytes in read buffer, after we should have tried to parse'
        peer.die()
    if peer.handshake:
        print 'switching to do_nothing_strategy'
        peer.strategy = do_nothing_strategy
        peer.send_msg(msg.handshake(info_hash=peer.torrent.info_hash, peer_id=peer.torrent.client.client_id))
        peer.send_msg(msg.bitfield(peer.torrent.bitfield))
        peer.send_msg(msg.unchoke())

