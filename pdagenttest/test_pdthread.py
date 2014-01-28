
import time
import unittest

from pdagent.pdthread import RepeatingThread


def _start_repeating_thread(f, *args):
    class T(RepeatingThread):
        def tick(self):
            f()
    t = T(*args)
    t.start()
    return t


class RepeatingThreadTest(unittest.TestCase):

    def test_basic(self):
        l = []

        def f():
            l.append(42)
        t = _start_repeating_thread(f, 1)
        try:
            time.sleep(0.1)
            # check that tick() is run once immediately on startup
            self.assertEquals(l, [42])
            time.sleep(1.0)
            self.assertEquals(l, [42, 42])
        finally:
            t.stop_and_join()
        # sanity test stopped
        time.sleep(1.0)
        self.assertEquals(l, [42, 42])

    def test_quick_stop(self):
        def f():
            pass
        t = _start_repeating_thread(f, 5)
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
        l = []

        def f():
            l.append(42)
            time.sleep(0.5)

        t = _start_repeating_thread(f, 1, False)
        try:
            time.sleep(0.1)
            self.assertEquals(l, [42])
            time.sleep(1.0)
            self.assertEquals(l, [42])
            time.sleep(0.5)
            self.assertEquals(l, [42, 42])
            time.sleep(1.5)
            self.assertEquals(l, [42, 42, 42])
        finally:
            t.stop_and_join()

        l = []
        t = _start_repeating_thread(f, 1, True)
        try:
            time.sleep(0.1)
            self.assertEquals(l, [42])
            time.sleep(1.0)
            self.assertEquals(l, [42, 42])
            time.sleep(1.0)
            self.assertEquals(l, [42, 42, 42])
        finally:
            t.stop_and_join()

    def test_change_sleep_time(self):
        def f():
            l.append(42)
        l = []

        t = _start_repeating_thread(f, 1)
        try:
            time.sleep(0.1)
            self.assertEquals(l, [42])
            t.set_sleep_secs(2)
            time.sleep(1.0)
            self.assertEquals(l, [42, 42])
            time.sleep(1.0)
            self.assertEquals(l, [42, 42])
            time.sleep(1.0)
            self.assertEquals(l, [42, 42, 42])
        finally:
            t.stop_and_join()

    def test_tick_exception(self):
        def f():
            l.append(42)
            raise Exception("foo")
        l = []
        t = _start_repeating_thread(f, 1)
        try:
            time.sleep(0.1)
            self.assertEquals(l, [42])
            time.sleep(1.0)
            self.assertFalse(t.is_alive())
        finally:
            t.stop_and_join()

    def test_strict_drops_extra_runs(self):
        def f():
            l.append(1)
            if slow:
                time.sleep(3)
            l.append(2)
        l = []
        slow = True
        t = _start_repeating_thread(f, 1, True)
        try:
            time.sleep(0.1)
            self.assertEquals(l, [1])
            time.sleep(3.0)
            self.assertEquals(l, [1, 2, 1])
            slow = False
            time.sleep(3.0)
            # 6.1 seconds in we should have run 7 times but first 2 were slow
            # we want to have run only once to catch up, not 5 times
            self.assertEquals(l, [1, 2, 1, 2, 1, 2])
        finally:
            t.stop_and_join()

if __name__ == "__main__":
    unittest.main()
