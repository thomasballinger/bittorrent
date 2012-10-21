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

DEFAULT_TIMEOUT = .3 # how long after a timer comes up it may be delayed
DEFAULT_TIMER_SLEEP = .3

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
        try: self.wait_for_read.remove(fd)
        except KeyError: pass
    def unreg_write(self, fd):
        if not isinstance(fd, int): fd = fd.fileno()
        try: self.wait_for_write.remove(fd)
        except KeyError: pass
    def start_timer(self, delay, dinger):
        self.timers.append((time.time() + delay, dinger))
    def cancel_timers(self, dinger):
        """Takes an object which impements .timer_event()"""
        self.timers = filter(lambda (t, x): x != dinger, self.timers)
    def add_readerwriter(self, fd, readerwriter):
        self.fd_map[fd] = readerwriter
    def poll(self, timeout=DEFAULT_TIMEOUT, timer_sleep=DEFAULT_TIMER_SLEEP):
        """Triggers every timer, and the first read or write event that is up

        Returns False if no events were hit
        Returns None if no events are registered
        timeout is the timeout passed to select in seconds
        timer_sleep is the time slept if no select is necessary because we're just
          using timers, (no io registered) to prevent thrashing the cpu
        """
        if not any([self.wait_for_read, self.wait_for_write, self.timers]):
            return None
        if not any([self.wait_for_read, self.wait_for_write]):
            time.sleep(timer_sleep)
            return False

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
        read_fds, write_fds, err_fds = select.select(self.wait_for_read, self.wait_for_write, [], timeout)
        if not any([read_fds, write_fds, err_fds]):
            return False
        for fd in read_fds:
            self.fd_map[fd].read_event()
            return self.fd_map[fd]
        for fd in write_fds:
            self.fd_map[fd].write_event()
            return self.fd_map[fd]
        return False
