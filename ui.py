
import threading
import sys
import time

class console(threading.Thread):
    def __init__(self, client):
        threading.Thread.__init__(self)
        self.client = client
        self.die = False

    def run(self):
        while True:
            print self.client
            print self.client.torrents
            s = raw_input('> ')
            if s == 'die':
                self.die = True


            if self.die:
                sys.exit()

