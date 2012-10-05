import bencode
import urllib
import sha
import time
import socket

client_id = (str(time.time()) + '20-byte string used as a unique ID for the client')[:20]
port = 6881

def get_our_addr_used(host):
    """Returns the ip address used on our side to contact host"""
    # doesn't work for localhost! Returns 192.168.0.16 instead of 127.0.0.1

    # see http://en.wikipedia.org/wiki/Discard_Protocol for why port 9
    # see http://stackoverflow.com/questions/7334349/
    # python-get-local-ip-address-used-to-send-ip-data-to-a-specific-remote-ip-addres
    # for discussion of problem
    client_ip = 'unknown'
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((host, 9))
    client_ip = s.getsockname()[0]
    s.close()
    print 'our ip:', client_ip
    return client_ip

def announce(torrent):
    """Returns data from Tracker specified in torrent file"""

    torrent_dict = bencode.bdecode(open(torrent).read())
    bencoded_info_dict = bencode.bencode(torrent_dict['info'])

    announce_query_params = {
        'info_hash' : sha.new(bencoded_info_dict).digest(),
        'peer_id' : client_id,
        'port' : port,
        'uploaded' : 0,
        'downloaded' : 0,
        'left' : '10000',
        'compact' : 1, # sometimes optional
        #'no_peer_id' :  # ignored if compact enabled
        'event' : 'started',
        #'ip' : ip # optional
        #'numwant' : 50 # optional
        #'trackerid' : tracker id, if included before # optional
    }

    addr = torrent_dict['announce']
    full_url = addr + '?' + urllib.urlencode(announce_query_params)
    response_data = bencode.bdecode(urllib.urlopen(full_url).read())

    peers_data = response_data['peers']
    peer_addresses = []
    for sixbits in [peers_data[i:i+6] for i in range(0,len(peers_data),6)]:
        peer_addresses.append(('.'.join(str(ord(ip_part)) for ip_part in sixbits[:4]), 256*ord(sixbits[4])+ord(sixbits[5])))

    #TODO fill out with our listening addr if we can figure it out
    our_ip = '127.0.0.1'
    peer_addresses = [x for x in peer_addresses if x[0] != our_ip or x[1] != port]
    response_data['peers'] = peer_addresses
    return response_data


announce_data = announce('/Users/tomb/Desktop/test.torrent')
print announce_data
#announce('/Users/tomb/Downloads/Tom Talks - Alex Jones and Batman [mininova].torrent')

if __name__ == '__main__':
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

