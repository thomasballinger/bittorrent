bittorrent client

requirements:
bencode
bitarray

deluge and opentracker on a linode instance are working for testing

Behaviors:
Peer can set each torrent to downloading, seeding, or both
torrent.seeding = True, torrent.downloading = True
Torrents Have Behaviors:
Behaviors can be functions that get called a lot, which
maintain state. They needn't be methods. On every read/write event
for instance, and perhaps also on a timer

Reactor needs timer events
Torrent behaviors get called on timer events

peer.send_msg needs to take care of housekeeping for these messages
individual messages need to time out, this housekeeping needs to
happen even if now 

Todo
----

* Maintain whether connection should be kept open, and keep it open if so
* Figure out which peers to get which file pieces from
    (random is reasonable acc. to spec)
* choose file pieces more intelligently
* actually check hashes - so figure out when pieces are done
* listen on socket for peer connections
* file access instead of in-memory file construction
* game theory algorithms - karma
* change announce params
* endgame cancel messages
* correctly not be interested when peer has nothing we want
* make sure being choked / being unchoked works ok
* Read about and play with request size - presumably piece size is a max
  spec: >2^17 not allowed, generally 2^15 or 14 unless end of file
* multiple file construction
* Can requests spill across pieces?
* Use more memory-efficient bitmaps (SBA)
* profile to see if send operations are blocking (consider sending less data per)
* Play with pipelineing for max DL speed
* writing testing scripts
* write tests for bittorrent logic - fake messages so no network io
* factor things out enough that Twisted could be used as a core
* learn twisted
* Build a frontend visualization of data - urwid or html+js
