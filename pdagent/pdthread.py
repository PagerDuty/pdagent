
import logging
from threading import Thread
import time


logger = logging.getLogger(__name__)


class RepeatingThread(Thread):

    def __init__(self, sleep_secs, strict=False):
        Thread.__init__(self, name=self.__class__.__name__)
        assert sleep_secs >= 1.0
        self._sleep_secs = sleep_secs
        self._strict = strict
        self._stop = False
        logger.info(
            "%s created with sleep_secs=%s" % (self.getName(), sleep_secs)
            )

    def run(self):
        next_run_time = 0
        while not self._stop:
            s = next_run_time - time.time()
            if s <= 0:
                self.tick()
                if self._strict:
                    # drop extra missed ticks if we fall behind
                    next_run_time = max(
                        next_run_time + self._sleep_secs, time.time()
                        )
                    # the above logic ruins clock alignment but it's
                    # simpler than trying to do float modulo math :)
                else:
                    next_run_time = time.time() + self._sleep_secs
            elif s < 1.0:
                time.sleep(s)
            else:
                # Sleep for only 1 sec to allow graceful stop
                time.sleep(1.0)

    def set_sleep_secs(self, sleep_secs):
        assert sleep_secs >= 1.0
        if sleep_secs != self._sleep_secs:
            self._sleep_secs = sleep_secs
            logger.info(
                "%s changed sleep_secs to %s" % (self.getName(), sleep_secs)
            )

    def stop(self):
        self._stop = True

    def stop_and_join(self):
        self.stop()
        self.join()

    def is_stop_invoked(self):
        return self._stop

    def tick(self):
        "You must override this method. It will be called repeatedly"
        raise NotImplementedError
