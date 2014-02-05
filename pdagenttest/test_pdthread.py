
import time
import unittest

from pdagent.pdthread import RepeatingThread


def _start_repeating_thread(f, delay_secs, is_absolute):
    class T(RepeatingThread):
        def tick(self):
            f()
    t = T(delay_secs, is_absolute)
    t.start()
    return t


class RepeatingThreadTest(unittest.TestCase):

    def test_basic(self):
        trace = []

        def f():
            trace.append(42)
        t = _start_repeating_thread(f, 1, False)
        try:
            time.sleep(0.1)
            # check that tick() is run once immediately on startup
            self.assertEquals(trace, [42])
            time.sleep(1.0)
            self.assertEquals(trace, [42, 42])
        finally:
            t.stop_and_join()
        # sanity test stopped
        time.sleep(1.0)
        self.assertEquals(trace, [42, 42])

    def test_quick_stop(self):
        def f():
            pass
        t = _start_repeating_thread(f, 5, False)
        try:
            time.sleep(0.1)
            t.stop()
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
            self.assertEquals(trace, [42])
            time.sleep(1.0)
            self.assertEquals(trace, [42])
            time.sleep(0.5)
            self.assertEquals(trace, [42, 42])
            time.sleep(1.5)
            self.assertEquals(trace, [42, 42, 42])
        finally:
            t.stop_and_join()

        trace = []
        t = _start_repeating_thread(f, 1, True)
        try:
            time.sleep(0.1)
            self.assertEquals(trace, [42])
            time.sleep(1.0)
            self.assertEquals(trace, [42, 42])
            time.sleep(1.0)
            self.assertEquals(trace, [42, 42, 42])
        finally:
            t.stop_and_join()

    def test_change_delay_secs(self):
        def f():
            trace.append(42)
        trace = []

        t = _start_repeating_thread(f, 1, False)
        try:
            time.sleep(0.1)
            self.assertEquals(trace, [42])
            t.set_delay_secs(2)
            time.sleep(1.0)
            self.assertEquals(trace, [42, 42])
            time.sleep(1.0)
            self.assertEquals(trace, [42, 42])
            time.sleep(1.0)
            self.assertEquals(trace, [42, 42, 42])
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
            self.assertEquals(trace, [42])
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
            self.assertEquals(trace, [1])
            time.sleep(3.0)
            self.assertEquals(trace, [1, 2, 1])
            slow = False
            time.sleep(3.0)
            # 6.1 seconds in we should have run 7 times but first 2 were slow
            # we want to have run only once to catch up, not 5 times
            self.assertEquals(trace, [1, 2, 1, 2, 1, 2])
        finally:
            t.stop_and_join()

if __name__ == "__main__":
    unittest.main()
