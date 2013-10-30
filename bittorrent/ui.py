
import threading
import sys
from bpython import cli

class console(threading.Thread):
    def __init__(self, client):
        threading.Thread.__init__(self)
        self.daemon = True
        self.client = client
        self.die = False

    def run(self):
        client = self.client
        cli.main(locals_=locals())
