import msg
import socket

from torrent import Torrent

t = Torrent('flagfromserver.torrent')
print t.info_hash

def connect():
    s = socket.socket()
    s.connect(('', 6882))
    s.send(str(msg.handshake(info_hash=t.info_hash, peer_id='b'*20)))
    print s.getsockname()
    print s.getpeername()
    return s

from bpython import cli
cli.main(locals_=locals())
