
from threading import Thread
import time


class RepeatingThread(Thread):

    def __init__(self, sleep_secs, drift=True):
        Thread.__init__(self)
        self.set_sleep_secs(sleep_secs)
        self._drift = drift
        self._stop = False

    def run(self):
        next_run_time = time.time()
        while not self._stop:
            t = time.time()
            if t >= next_run_time:
                self.tick()
                t = time.time()
                if self._drift:
                    next_run_time = t + self._sleep_secs
                else:
                    next_run_time += self._sleep_secs
                    if next_run_time < t:
                        # drop extra missed ticks if we fall behind
                        next_run_time = t
            else:
                s = next_run_time - t
                time.sleep(s if s < 1.0 else 1.0)

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
