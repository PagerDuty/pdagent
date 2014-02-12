
import logging
from threading import Thread
import time


logger = logging.getLogger(__name__)


class RepeatingThread(Thread):
    """
    A thread that runs code repeatedly at a regular interval.

    To use:
    - understand the is_absolute parameter!
    - extend this class and override the tick() method
    - create instance of your class passing preferred parameters
    - remember to call start() to start the thread!

    Notes:
    - the first call to tick() will happen as soon as you start the thread
    - normally you do not override the run() method
    """

    def __init__(self, delay_secs, is_absolute):
        """
        Create a RepeatingThread with given settings.

        delay_secs = the interval between calls to tick()
        is_absolute = whether interval is "absolute" or "relative"

        When is_absolute=False, the thread will always sleep for delay_secs
        between calls to tick().  E.g. if delay_secs is 5 seconds and a tick()
        takes 3 seconds, the thread will sleep for 5 seconds so the next call
        to tick() will end up *starting* 8 seconds after the *start* of the
        previous call.

        When is_absolute=True, the thread will try to call tick() at the given
        interval in absolute clock time. If a call to tick() takes longer than
        delay_secs, the next call will happen immediately.  (the clock
        alignment will also drift in this case - see implementation and unit
        tests for details)  E.g. if delay_secs is 5 seconds and a tick() takes
        3 seconds, the thread will sleep only 2 seconds so that the next call
        to tick() will *start* 5 seconds after the *start* of the previous
        call. If a tick() takes even longer - i.e. more than 2 * delay_secs -
        the extra missed calls are lost.

        """
        Thread.__init__(self, name=self.__class__.__name__)
        assert delay_secs >= 1.0
        self._delay_secs = delay_secs
        self._is_absolute = is_absolute
        self._stop = False
        logger.info(
            "%s created with delay_secs=%s" % (self.getName(), delay_secs)
            )

    def tick(self):
        "You must override this method. It will be called repeatedly"
        raise NotImplementedError

    def run(self):
        next_run_time = 0
        try:
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
        except:
            logger.error("Error in run(); Stopping.", exc_info=True)

    def set_delay_secs(self, delay_secs):
        """
        Change the interval.

        Currently, this value is used just after the end of a call to tick()
        so it will not change a sleep interval that's already in progress.
        """
        assert delay_secs >= 1.0
        if delay_secs != self._delay_secs:
            self._delay_secs = delay_secs
            logger.info(
                "%s changed delay_secs to %s" % (self.getName(), delay_secs)
            )

    def stop(self):
        """
        Ask the thread to stop.

        This call does NOT block. If the thread is in the sleeping interval it
        checks for this stop signal every 1 second.  If the thread is in the
        call to tick() it will only stop after tick() is complete.  (You can
        check self._stop in tick() if you wish to support stopping there)
        """
        self._stop = True

    def stop_and_join(self):
        "Helper function - equivalent to calling stop() and then join()"
        self.stop()
        self.join()

    def is_stop_invoked(self):
        return self._stop
