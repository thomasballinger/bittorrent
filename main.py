import logging

from client import BittorrentClient
import torrentstrategy

def leech(torrentfilename):
    client = BittorrentClient()
    torrent = client.add_torrent(torrentfilename)
    torrent.strategy = torrentstrategy.connect_and_ask_n_peers(15)
    loop(client)

def seed(torrentfile, datafile):
    client = BittorrentClient(6882)
    torrent = client.add_torrent(torrentfile)
    torrent.load(datafile)
    torrent.tracker_update()
    loop(client)

def loop(client):
    while True:
        r = client.reactor.poll(1)
        if r is None:
            return

def CLI():
    logging.basicConfig(filename='bt.log', level=logging.INFO)
    logging.info('starting logging')

    import sys
    #torrentfile = 'test.torrent'
    #torrentfile = '/Users/tomb/Downloads/How To Speed Up Your BitTorrent Downloads [mininova].torrent'
    #torrentfile = 'soulpurge.torrent'
    torrentfile = 'world.torrent'
    #torrentfile = 'flagfromserver.torrent'
    datafile = 'flag.jpg'
    if len(sys.argv) > 1 and sys.argv[1] == 'seed':
        seed(torrentfile, datafile)
    else:
        leech(torrentfile)

if __name__ == '__main__':
    CLI()
