from client import BittorrentClient
import torrentstrategy


def main():
    client = BittorrentClient()
    #torrent = client.add_torrent('flagfromserver.torrent')
    #torrent = client.add_torrent('test.torrent')
    #torrent = client.add_torrent('/Users/tomb/Downloads/How To Speed Up Your BitTorrent Downloads [mininova].torrent')
    torrent = client.add_torrent('/Users/tomb/Downloads/soulpurge - broken heart ep.torrent')
    torrent.strategy = torrentstrategy.connect_and_ask_n_peers(15)
    loop(client)

def loop(client):
    while True:
        r = client.reactor.poll(1)
        if r is None:
            return

if __name__ == '__main__':
    main()
