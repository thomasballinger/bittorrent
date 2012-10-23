
from main import BittorrentClient

def have():
    client = BittorrentClient(6882)
    torrent = client.add_torrent('flagfromserver.torrent')
    torrent.load('flag.jpg')
    torrent.tracker_update()
    while True:
        r = client.reactor.poll(1)
        if r is None:
            return

have()
