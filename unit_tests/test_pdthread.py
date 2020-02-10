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
import time
import unittest

from pdagent.pdthread import RepeatingTask, RepeatingTaskThread


logging.basicConfig(level=logging.CRITICAL)


def _start_repeating_thread(f, interval_secs, is_absolute):
    class T(RepeatingTask):
        def tick(self):
            f()
    t = RepeatingTaskThread(T(interval_secs, is_absolute))
    t.start()
    return t


class RepeatingTaskThreadTest(unittest.TestCase):

    def test_basic(self):
        trace = []

        def f():
            trace.append(42)
        t = _start_repeating_thread(f, 1, False)
        try:
            time.sleep(0.1)
            # check that tick() is run once immediately on startup
            self.assertEqual(trace, [42])
            time.sleep(1.0)
            self.assertEqual(trace, [42, 42])
        finally:
            t.stop_and_join()
        # sanity test stopped
        time.sleep(1.0)
        self.assertEqual(trace, [42, 42])

    def test_quick_stop(self):
        def f():
            pass
        t = _start_repeating_thread(f, 5, False)
        try:
            time.sleep(0.1)
            t.stop_async()
            time.sleep(0.1)
            self.assertTrue(t.is_alive())
            time.sleep(1.0)
            self.assertFalse(t.is_alive())
        finally:
            t.stop_and_join()

    def test_strict(self):
        trace = []

        def f():
            trace.append(42)
            time.sleep(0.5)

        t = _start_repeating_thread(f, 1, False)
        try:
            time.sleep(0.1)
            self.assertEqual(trace, [42])
            time.sleep(1.0)
            self.assertEqual(trace, [42])
            time.sleep(0.5)
            self.assertEqual(trace, [42, 42])
            time.sleep(1.5)
            self.assertEqual(trace, [42, 42, 42])
        finally:
            t.stop_and_join()

        trace = []
        t = _start_repeating_thread(f, 1, True)
        try:
            time.sleep(0.1)
            self.assertEqual(trace, [42])
            time.sleep(1.0)
            self.assertEqual(trace, [42, 42])
            time.sleep(1.0)
            self.assertEqual(trace, [42, 42, 42])
        finally:
            t.stop_and_join()

    def test_strict_first_run(self):
        trace = []

        def f():
            trace.append(42)
            time.sleep(1.0)

        t = _start_repeating_thread(f, 2, True)
        try:
            time.sleep(0.1)
            self.assertEqual(trace, [42])
            time.sleep(1.0)
            self.assertEqual(trace, [42])
            time.sleep(1.0)
            self.assertEqual(trace, [42, 42])
        finally:
            t.stop_and_join()

    def test_change_interval_secs(self):
        def f():
            trace.append(42)
        trace = []

        t = _start_repeating_thread(f, 1, False)
        try:
            time.sleep(0.1)
            self.assertEqual(trace, [42])
            t._rtask.set_interval_secs(2)
            time.sleep(1.0)
            self.assertEqual(trace, [42, 42])
            time.sleep(1.0)
            self.assertEqual(trace, [42, 42])
            time.sleep(1.0)
            self.assertEqual(trace, [42, 42, 42])
        finally:
            t.stop_and_join()

    def test_tick_exception(self):
        def f():
            trace.append(42)
            raise Exception("foo")
        trace = []
        t = _start_repeating_thread(f, 1, False)
        try:
            time.sleep(0.1)
            self.assertEqual(trace, [42])
            time.sleep(1.0)
            self.assertFalse(t.is_alive())
        finally:
            t.stop_and_join()

    def test_strict_drops_extra_runs(self):
        def f():
            trace.append(1)
            if slow:
                time.sleep(3)
            trace.append(2)
        trace = []
        slow = True
        t = _start_repeating_thread(f, 1, True)
        try:
            time.sleep(0.1)
            self.assertEqual(trace, [1])
            time.sleep(3.0)
            self.assertEqual(trace, [1, 2, 1])
            slow = False
            time.sleep(3.0)
            # 6.1 seconds in we should have run 7 times but first 2 were slow
            # we want to have run only once to catch up, not 5 times
            self.assertEqual(trace, [1, 2, 1, 2, 1, 2])
        finally:
            t.stop_and_join()

if __name__ == "__main__":
    unittest.main()
