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
* actually check hashes - so figure out when pieces are done
* file access instead of in-memory file construction
* throw away data in memory after write (need to use representation
    other than a byte array
* multiple file construction
* if peer dies, return all pending requests
* timeout cancel messages

---done above this line---

* Don't ask if they don't have the piece
* endgame cancel messages
* Use more memory-efficient bitmaps (SBA)
* make sure being choked / being unchoked works ok
* correctly not be interested when peer has nothing we want
* Read about and play with request size - presumably piece size is a max
    spec: >2^17 not allowed, generally 2^15 or 14 unless end of file
* look at the problems we were having with high pipeline number
    and lower timed out request time

------the I'm Done line------

* Figure out which peers to get which file pieces from
    (random is reasonable acc. to spec)
* game theory algorithms - karma
* change announce params, update more than once
* strategy for torrent choosing peers, keep records of which peers worked, keep
    ask tracker for new peers periodically
* Can requests spill across pieces?
* profile to see if send operations are blocking (consider sending less data per)
* Play with pipelineing for max DL speed
* writing testing scripts
* write tests for bittorrent logic - fake messages so no network io
* factor things out enough that Twisted could be used as a core
* learn twisted
* Build a frontend visualization of data - urwid or html+js
