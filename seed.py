
from main import BittorrentClient

def have():
    client = BittorrentClient(6882)
    torrent = client.add_torrent('localtest.torrent')
    torrent.load('/Users/tomb/Dropbox/Camera Uploads/2012-10-16 23.32.57.jpg')
    torrent.tracker_update()
    while True:
        r = client.reactor.poll(1)
        if r is None:
            return

have()
