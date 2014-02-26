#
# Copyright (c) 2013-2014, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the copyright holder nor the
#     names of its contributors may be used to endorse or promote products
#     derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

import logging
from threading import Thread
import time


logger = logging.getLogger(__name__)


class RepeatingTask:
    """
    Code that runs repeatedly at a regular interval.

    To use:
    - understand the is_absolute parameter!
    - extend this class and override the tick() method
    - create instance of your class passing preferred parameters
    - pass the task to a task runner e.g. RepeatingTaskThread
    """

    def __init__(self, interval_secs, is_absolute):
        """
        Create a RepeatingTask with given settings.

        interval_secs = the interval between calls to tick()
        is_absolute = whether interval is "absolute" or "relative"

        When is_absolute=False, the task wants interval_secs to be the time
        interval between the *end* of one call and the *start* of the next call
        to tick().  E.g. if interval_secs is 5 seconds and a tick() takes 3
        seconds, the next call to tick() should *start* 8 seconds after
        the *start* of the previous call.

        When is_absolute=True, the task wants interval_secs to be the time
        interval between the *start* of one call and the *start* of the next
        call to tick(). E.g. if interval_secs is 5 seconds and a tick() takes
        3 seconds, the next call should happen in 2 seconds. If a call to
        tick() takes longer than interval_secs, it is expected that the next
        call should happen immediately as it is overdue. However, you should
        check the implementations details of the task runner used to run the
        task for details on how overdue calls are handled.
        """
        assert interval_secs >= 1
        self._interval_secs = interval_secs
        self._is_absolute = is_absolute
        self._stop = False
        logger.info(
            "%s created with interval_secs %s"
            % (self.get_name(), interval_secs)
            )

    def tick(self):
        """
        You must override this method.

        It will be called repeatedly. You can use self.is_stop_invoked()
        in this method to see if a stop has been requested.
        """
        raise NotImplementedError

    def set_interval_secs(self, interval_secs):
        assert interval_secs >= 1
        if interval_secs != self._interval_secs:
            self._interval_secs = interval_secs
            logger.info(
                "%s changed interval_secs to %s"
                % (self.get_name(), interval_secs)
                )

    def stop_async(self):
        "Ask a task to exit early from a tick()."
        self._stop = True

    def get_name(self):
        # Override this method to implement a custom name
        return self.__class__.__name__

    def get_interval_secs(self):
        return self._interval_secs

    def is_absolute(self):
        return self._is_absolute

    def is_stop_invoked(self):
        return self._stop


class RepeatingTaskThread(Thread):
    """
    A thread that runs a RepeatingTask.

    To use:
    - create an instance wrapping your task
    - call start() to start the thread

    Notes:
    - the first call to tick() will happen as soon as you start the thread
    - the task's interval_secs is sampled just after the end of a tick()

    Handling of is_absolute=True:
    If a call to tick() takes longer than interval_secs, the next call will
    happen immediately. If a call takes long enough that more than one call is
    overdue, the extra missed calls are lost. In all overdue cases, clock
    alignment will be lost. See implementation and unit tests for details.
    """

    def __init__(self, repeating_task):
        assert isinstance(repeating_task, RepeatingTask)
        Thread.__init__(self, name=repeating_task.get_name())
        self._rtask = repeating_task
        self._stop = False
        logger.info("RepeatingTaskThread created for %s" % self.getName())

    def run(self):
        next_run_time = time.time()
        try:
            while not self._stop:
                s = next_run_time - time.time()
                if s <= 0:
                    self._rtask.tick()
                    if self._rtask.is_absolute():
                        # drop extra missed ticks if we fall behind
                        next_run_time = max(
                            next_run_time + self._rtask.get_interval_secs(),
                            time.time()
                            )
                        # the above logic ruins clock alignment but it's
                        # simpler than trying to do float modulo math :)
                    else:
                        next_run_time = \
                            time.time() + self._rtask.get_interval_secs()
                else:
                    # Sleep at most 1 sec at a time to allow graceful stop
                    time.sleep(min(s, 1.0))
        except:
            logger.error("Error in run(); Stopping.", exc_info=True)

    def stop_async(self):
        """
        Ask the thread to stop.

        This call does NOT block. This method will call the task's stop()
        method to let the task know about the stop request. If the thread is
        in the interval between task runs it checks for this stop signal every
        1 second. If the thread is in the task's tick() it will only stop after
        tick() is complete.
        """
        self._stop = True
        self._rtask.stop_async()

    def stop_and_join(self):
        "Helper function - equivalent to calling stop() and then join()"
        self.stop_async()
        self.join()

