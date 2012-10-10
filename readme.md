bittorrent client

requirements:
bencode
bitarray

Todo
----

* create local environment for testing - opentracker or something else
    * opentracker + uTorrent isn't currently working
    * something scriptable would be good
* implement logic for getting rest of file, keeping connection up in Peer
* prettier message parsing / writing
* allow sending of chunks of a file
* allow simultaneous torrent files
* factor things out enough that Twisted could be used as a core
* nice doctests on parsing libraries
* learn twisted
