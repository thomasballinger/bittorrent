
from main import BittorrentClient
import sha

def have():
    client = BittorrentClient(6882)
    torrent = client.add_torrent('flagfromserver.torrent')
    torrent.load('flag.jpg')
    torrent.tracker_update()
    torrent.data[100] = 1
    while True:
        r = client.reactor.poll(1)
        if r is None:
            return

def repl():
    from bpython import cli; cli.main(locals_=locals())

have()


