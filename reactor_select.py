"""Reactor with socket.select

First, instantiate a reactor.

Next, register a file descriptor integer and corresponding
object with the reactor.

Then, register read or write on the integer (and therefore object)
in order to have that object called on that read or write event

Implement the read_event / write_event interface in that object

Unregister read or write if you don't want the notification to happen again

A read_event or write_event should never cause a readerwriter to dissappear,
because there could be another event in the queue for it, retrieved in the
same batch of messages. In this case a reference to that object would
still be hanging around.

Timers: start_timer(seconds, object-which-implements-timer_event())
cancel_timers(objects-which-you-started-one-or-more-timers-for-earlier)

Timer objects, on the other hand, may cause things to dissapear.
Only one timer event is ever retrieved at a time, so there's still
time to cancel an object's timers, and therefore possible to destroy it.

"""

import select
import time

MAX_DELAY = 1 # how long after a timer comes up it may be delayed

class Reactor(object):
    def __init__(self):
        self.fd_map = {}
        self.wait_for_read = set()
        self.wait_for_write = set()
        self.timers = []
    def reg_read(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        self.wait_for_read.add(fd)
    def reg_write(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        self.wait_for_write.add(fd)
    def unreg_read(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        self.wait_for_read.remove(fd)
    def unreg_write(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        self.wait_for_write.remove(fd)
    def start_timer(self, delay, dinger):
        self.timers.append((time.time() + delay, dinger))
    def cancel_timers(self, delay, dinger):
        self.timers = filter(lambda (t, x): dinger)
    def add_readerwriter(self, fd, readerwriter):
        self.fd_map[fd] = readerwriter
    def poll(self):
        """Triggers every timer, read or write event that is up"""
        now = time.time()
        while True:
            self.timers.sort(key=lambda x: x[0])
            timerlist = self.timers[:]
            for t, dinger in timerlist:
                if t < now:
                    self.timers.remove((t, dinger))
                    dinger.timer_event()
                    break
            else:
                break
        if not any([self.wait_for_read, self.wait_for_write]):
            return False
        read_fds, write_fds, err_fds = select.select(self.wait_for_read, self.wait_for_write, [], MAX_DELAY)
        if not any([read_fds, write_fds, err_fds]):
            return False
        for fd in read_fds:
            self.fd_map[fd].read_event()
        for fd in write_fds:
            self.fd_map[fd].write_event()
