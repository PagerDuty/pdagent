
import logging
from threading import Thread
import time


logger = logging.getLogger(__name__)


class RepeatingThread(Thread):

    def __init__(self, delay_secs, is_absolute):
        Thread.__init__(self, name=self.__class__.__name__)
        assert delay_secs >= 1.0
        self._delay_secs = delay_secs
        self._is_absolute = is_absolute
        self._stop = False
        logger.info(
            "%s created with delay_secs=%s" % (self.getName(), delay_secs)
            )

    def run(self):
        next_run_time = 0
        while not self._stop:
            s = next_run_time - time.time()
            if s <= 0:
                self.tick()
                if self._is_absolute:
                    # drop extra missed ticks if we fall behind
                    next_run_time = max(
                        next_run_time + self._delay_secs, time.time()
                        )
                    # the above logic ruins clock alignment but it's
                    # simpler than trying to do float modulo math :)
                else:
                    next_run_time = time.time() + self._delay_secs
            elif s < 1.0:
                time.sleep(s)
            else:
                # Sleep for only 1 sec to allow graceful stop
                time.sleep(1.0)

    def set_delay_secs(self, delay_secs):
        assert delay_secs >= 1.0
        if delay_secs != self._delay_secs:
            self._delay_secs = delay_secs
            logger.info(
                "%s changed sleep_secs to %s" % (self.getName(), delay_secs)
            )

    def stop(self):
        self._stop = True

    def stop_and_join(self):
        self.stop()
        self.join()

    def tick(self):
        "You must override this method. It will be called repeatedly"
        raise NotImplementedError
