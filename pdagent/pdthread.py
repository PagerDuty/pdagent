
from threading import Thread
import time


class RepeatingThread(Thread):

    def __init__(self, sleep_secs, strict=False):
        Thread.__init__(self, name=self.__class__.__name__)
        self.set_sleep_secs(sleep_secs)
        self._strict = strict
        self._stop = False

    def run(self):
        next_run_time = 0
        while not self._stop:
            s = next_run_time - time.time()
            if s <= 0:
                self.tick()
                if self._strict:
                    next_run_time += self._sleep_secs
                    if next_run_time < time.time():
                        # drop extra missed ticks if we fall behind
                        next_run_time = time.time()
                        # the above logic ruins clock alignment but it's
                        # simpler than trying to do float modulo math :)
                else:
                    next_run_time = time.time() + self._sleep_secs
            elif s < 1.0:
                time.sleep(s)
            else:
                time.sleep(1.0)

    def set_sleep_secs(self, sleep_secs):
        assert sleep_secs >= 1.0
        self._sleep_secs = sleep_secs

    def stop(self):
        self._stop = True

    def stop_and_join(self):
        self.stop()
        self.join()

    def tick(self):
        "You must override this method. It will be called repeatedly"
        raise NotImplementedError
