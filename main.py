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

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('torrent', help='torrent file to download or seed')
    parser.add_argument('-s', '--seed', help='start in seeding mode', metavar='LOAD_DATA', default=False)
    parser.add_argument('-l', '--message-log', action='store_true',
            help='log everything; among other things, log all messages sent and received')
    parser.add_argument('-v', '--verbose', action='count', default=0,
            help='print messages to stderr in addition to bt.log. Add v\'s for more verbosity')
    args = parser.parse_args()

    logging.basicConfig(filename='bt.log', level=logging.DEBUG if args.message_log else logging.INFO)
    logging.info('starting logging')

    if args.verbose:
        console = logging.StreamHandler()
        console.setLevel(getattr(logging, ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'][args.verbose-1]))
        logging.getLogger('').addHandler(console)

    if args.seed:
        seed(args.torrent, args.seed)
    else:
        leech(args.torrent)

if __name__ == '__main__':
    CLI()
