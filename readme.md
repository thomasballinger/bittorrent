bittorrent client

requirements:
bencode
bitarray

deluge and opentracker on a linode instance are working for testing

Todo
----

* Maintain whether connection should be kept open, and keep it open if so
* Figure out which peers to get which file pieces from 
* choose file pieces more intelligently
* actually check hashes
* listen on socket for peer connections
* file access instead of in-memory file construction
* game theory algorithms - karma
* endgame cancel messages
* multiple file construction
* Read about and play with request size - presumably piece size is a max
  spec: >2^17 not allowed, generally 2^15 or 14 unless end of file
* Can requests spill across pieces?
* Use more memory-efficient
* Play with pipelineing for max DL speed
* writing testing scripts
* write tests for bittorrent logic - fake messages so no network io
* factor things out enough that Twisted could be used as a core
* learn twisted
* Build a frontend visualization of data - urwid or html+js
