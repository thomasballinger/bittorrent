from client import BittorrentClient

import torrentstrategy

def main():
    client = BittorrentClient()
    torrent = client.add_torrent('flagfromserver.torrent')
    #torrent = client.add_torrent('test.torrent')
    #torrent = client.add_torrent('/Users/tomb/Downloads/How To Speed Up Your BitTorrent Downloads [mininova].torrent')
    torrent.strategy = torrentstrategy.connect_and_ask_n_peers(15)

    while True:
        r = client.reactor.poll(1)
        print 'num peers:', len(torrent.peers)
        for peer in torrent.peers:
            peer.check_outstanding_requests()
        if r is None:
            return

if __name__ == '__main__':
    main()
