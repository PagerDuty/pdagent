
import os
import shutil
from threading import Lock, Thread
import time
import unittest

from pdagent.constants import \
    EVENT_CONSUMED, EVENT_NOT_CONSUMED, EVENT_BAD_ENTRY, EVENT_BACKOFF_SVCKEY, \
    EVENT_STOP_ALL
from pdagent.pdqueue import PDQueue, EmptyQueue


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_QUEUE_DIR = os.path.join(_TEST_DIR, "test_queue")
TEST_DB_DIR = os.path.join(_TEST_DIR, "test_db")


class NoOpLock:

    def __init__(self, lockfile):
        pass

    def acquire(self):
        pass

    def release(self):
        pass


class PDQueueTest(unittest.TestCase):

    config = {
        "outqueue_dir": TEST_QUEUE_DIR,
        "db_dir": TEST_DB_DIR,
        "backoff_initial_delay_sec": 1,
        "backoff_factor": 2,
        "backoff_max_attempts": 3
    }

    def setUp(self):
        if os.path.exists(TEST_QUEUE_DIR):
            shutil.rmtree(TEST_QUEUE_DIR)
        if os.path.exists(TEST_DB_DIR):
            shutil.rmtree(TEST_DB_DIR)

    def tearDown(self):
        if os.path.exists(TEST_QUEUE_DIR):
            shutil.rmtree(TEST_QUEUE_DIR)
        if os.path.exists(TEST_DB_DIR):
            shutil.rmtree(TEST_DB_DIR)

    def newQueue(self):
        return PDQueue(PDQueueTest.config, NoOpLock)

    def test__open_creat_excl_with_retry(self):
        from pdagent.pdqueue import _open_creat_excl
        q = self.newQueue()
        fname_abs = q._abspath("_open_creat_excl_with_retry.txt")
        fd1 = _open_creat_excl(fname_abs)
        self.assertNotEquals(fd1, None)
        fd2 = None
        try:
            fd2 = _open_creat_excl(fname_abs)
            self.assertEquals(fd2, None)
        finally:
            os.close(fd1)
            if fd2:
                os.close(fd2)

    def test_init_creates_directory(self):
        self.assertFalse(os.path.exists(TEST_QUEUE_DIR))
        self.newQueue()
        self.assertTrue(os.path.exists(TEST_QUEUE_DIR))

    def test_enqueue_and_dequeue(self):
        q = self.newQueue()

        self.assertEquals(q._queued_files(), [])

        f_foo = q.enqueue("svckey", "foo")
        self.assertEquals(q._queued_files(), [f_foo])
        self.assertEquals(open(q._abspath(f_foo)).read(), "foo")

        f_bar = q.enqueue("svckey", "bar")
        self.assertEquals(q._queued_files(), [f_foo, f_bar])
        self.assertEquals(open(q._abspath(f_foo)).read(), "foo")
        self.assertEquals(open(q._abspath(f_bar)).read(), "bar")

        def consume_foo(s):
            self.assertEquals("foo", s)
            return EVENT_CONSUMED
        q.dequeue(consume_foo)

        def consume_bar(s):
            self.assertEquals("bar", s)
            return EVENT_CONSUMED
        q.dequeue(consume_bar)

        # check queue is empty
        self.assertEquals(q._queued_files(), [])
        self.assertRaises(EmptyQueue, q.dequeue, lambda s: EVENT_CONSUMED)

    def test_dont_consume(self):
        # The item should stay in the queue if we don't consume it.
        q = self.newQueue()
        q.enqueue("svckey", "foo")

        def dont_consume_foo(s):
            self.assertEquals("foo", s)
            return EVENT_NOT_CONSUMED
        q.dequeue(dont_consume_foo)
        q.dequeue(dont_consume_foo)

        def consume_foo(s):
            self.assertEquals("foo", s)
            return EVENT_CONSUMED
        q.dequeue(consume_foo)

        self.assertRaises(EmptyQueue, q.dequeue, lambda s: EVENT_CONSUMED)

    def test_consume_error(self):
        # The item should get tagged as error, and not be available for
        # further consumption, if consumption causes error.
        q = self.newQueue()
        q.enqueue("svckey", "foo")

        def erroneous_consume_foo(s):
            self.assertEquals("foo", s)
            return EVENT_BAD_ENTRY
        q.dequeue(erroneous_consume_foo)

        self.assertEquals(len(q._queued_files("err_")), 1)
        self.assertRaises(EmptyQueue, q.dequeue, lambda s: EVENT_CONSUMED)

    def test_backoff(self):
        # The item and all other items for same service key must get backed off
        # until backoff limit is hit, then the offending item should get tagged
        # as error, and not be available for further consumption.
        q = self.newQueue()
        q.enqueue("svckey1", "foo")
        time.sleep(1)
        q.enqueue("svckey1", "bar")
        time.sleep(1)
        q.enqueue("svckey2", "baz")

        events_processed = []
        count = 0
        max_attempts = PDQueueTest.config["backoff_max_attempts"]
        sleep_time_sec = PDQueueTest.config["backoff_initial_delay_sec"]
        sleep_factor = PDQueueTest.config["backoff_factor"]

        def consume_with_backoff(s):
            events_processed.append(s)
            if count == 1 and s == "baz":
                # good service key.
                return EVENT_CONSUMED
            elif count <= max_attempts and s == "foo":
                # before back-off limit is reached for bad event.
                return EVENT_BACKOFF_SVCKEY | EVENT_BAD_ENTRY
            elif count == max_attempts and s == "bar":
                # next event after bad event is kicked out.
                return EVENT_CONSUMED
            else:
                self.fail(
                    "Unexpected event %s in attempt %d" % (s, count))

        self.assertEquals(len(q._queued_files()), 3)

        # flush once.
        count += 1
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(events_processed, ["foo", "baz"])  # 1 bad, 1 good
        self.assertEquals(len(q._queued_files()), 2)  # 2 from bad svckey
        self.assertEquals(len(q._queued_files("err_")), 0)  # no error yet.

        # retry immediately. later-retriable events must not be processed.
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(len(events_processed), 0)
        self.assertEquals(len(q._queued_files()), 2)
        self.assertEquals(len(q._queued_files("err_")), 0)

        # retry after retriable-time, up to max attempts.
        for i in range(2, max_attempts):
            time.sleep(sleep_time_sec)
            sleep_time_sec *= sleep_factor
            count += 1
            events_processed = []
            q.flush(consume_with_backoff)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(len(q._queued_files()), 2)  # 2 from bad svckey
            self.assertEquals(len(q._queued_files("err_")), 0)  # no error yet

        # retry now (max-th time). bad event should be kicked out.
        time.sleep(sleep_time_sec)
        count += 1
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(events_processed, ["foo", "bar"])  # bad + next events
        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(len(q._queued_files("err_")), 1)

        # and now, the queue must be empty.
        self.assertRaises(EmptyQueue, q.dequeue, lambda s: EVENT_CONSUMED)

    def test_stop_processing(self):
        # No later event must be processed.
        q = self.newQueue()
        q.enqueue("svckey1", "foo")
        time.sleep(1)
        q.enqueue("svckey1", "bar")
        time.sleep(1)
        q.enqueue("svckey2", "baz")

        events_processed = []
        count = 0

        def consume_with_stopall(s):
            events_processed.append(s)
            if count == 1 and s == "foo":
                # first time, we'll ask that no further events be processed.
                return EVENT_STOP_ALL
            elif count == 2:
                # next time, we'll consider it a success.
                return EVENT_CONSUMED
            else:
                self.fail(
                    "Unexpected event %s in attempt %d" % (s, count))

        self.assertEquals(len(q._queued_files()), 3)

        # flush once. later events must not be processed.
        count += 1
        events_processed = []
        q.flush(consume_with_stopall)
        self.assertEquals(events_processed, ["foo"])
        self.assertEquals(len(q._queued_files()), 3)  # 2 from bad svckey
        self.assertEquals(len(q._queued_files("err_")), 0)  # no error events

        # retry. all events must now be processed.
        count += 1
        events_processed = []
        q.flush(consume_with_stopall)
        self.assertEquals(events_processed, ["foo", "bar", "baz"])
        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(len(q._queued_files("err_")), 0)  # no error events

        # and now, the queue must be empty.
        self.assertRaises(EmptyQueue, q.dequeue, lambda s: EVENT_CONSUMED)

    def test_enqueue_never_blocks(self):
        # test that a read lock during dequeue does not block an enqueue
        q = self.newQueue()
        f_foo = q.enqueue("svckey", "foo")

        trace = []

        class LockClass:
            def __init__(self, lockfile):
                trace.append("Li")

            def acquire(self):
                trace.append("La")

            def release(self):
                trace.append("Lr")
        q.lock_class = LockClass

        def dequeue():
            try:
                def consume(s):
                    trace.append("C1")
                    time.sleep(0.2)
                    trace.append("C2")
                    return EVENT_CONSUMED
                q.dequeue(consume)
            except EmptyQueue:
                trace.append("q_EQ")

        thread_dequeue = Thread(target=dequeue)
        thread_dequeue.start()
        time.sleep(0.1)  # give the thread time to acquire the lock & sleep

        self.assertEquals(trace, ["Li", "La", "C1"])
        self.assertEquals(q._queued_files(), [f_foo])

        f_bar = q.enqueue("svckey", "bar")

        self.assertEquals(trace, ["Li", "La", "C1"])
        self.assertEquals(q._queued_files(), [f_foo, f_bar])

        time.sleep(0.2)

        self.assertEquals(trace, ["Li", "La", "C1", "C2", "Lr"])
        self.assertEquals(q._queued_files(), [f_bar])

    def test_parallel_dequeue(self):
        # test that a dequeue blocks another dequeue using locking

        q1 = self.newQueue()
        q2 = self.newQueue()
        q1.enqueue("svckey", "foo")

        dequeue_lockfile = q1._dequeue_lockfile
        trace = []
        lock = Lock()

        def make_lock_class(name):
            # so that pydev doesn't complain about self naming
            outer_self = self

            class LockClass:
                def __init__(self, lockfile):
                    outer_self.assertEquals(dequeue_lockfile, lockfile)

                def acquire(self):
                    trace.append(name + "_A1")
                    lock.acquire()
                    trace.append(name + "_A2")

                def release(self):
                    trace.append(name + "_R")
                    lock.release()
            return LockClass

        q1.lock_class = make_lock_class("q1")
        q2.lock_class = make_lock_class("q2")

        def dequeue2():
            try:
                def consume2(s):
                    self.fail()  # consume2 shouldn't be called!
                q2.dequeue(consume2)
            except EmptyQueue:
                trace.append("q2_EQ")

        thread_dequeue2 = Thread(target=dequeue2)

        def consume1(s):
            # check that q1 acquired the lock
            self.assertEquals(trace, ["q1_A1", "q1_A2"])
            # start dequeue2 in separate thread to recreate concurrent access
            thread_dequeue2.start()
            # give thread time to run - it should be stuck in lock acquire
            time.sleep(0.1)
            self.assertEquals(trace, ["q1_A1", "q1_A2", "q2_A1"])
            # consume the item
            trace.append("q1_C:" + s)
            return EVENT_CONSUMED

        q1.dequeue(consume1)
        # give the thread time to acquire the just released
        # lock & run to completion
        time.sleep(0.1)

        self.assertEquals(trace, [
            "q1_A1", "q1_A2", "q2_A1",
            "q1_C:foo", "q1_R",
            "q2_A2", "q2_R",
            "q2_EQ",
             ])

    def test_cleanup(self):
        # simulate enqueues done a while ago.
        q = self.newQueue()

        def enqueue_before(sec, prefix="pdq"):
            enqueue_time_ms = (int(time.time()) - sec) * 1000
            fname = "%s_%d_%s.txt" % (
                prefix,
                enqueue_time_ms,
                "svckey%d" % (enqueue_time_ms % 10))
            fpath = os.path.join(q.queue_dir, fname)
            os.close(os.open(fpath, os.O_CREAT))
            return fname

        # we'll first remove things enqueued >1500s ago, and then <1500s ago.
        q1 = enqueue_before(2000)
        t1 = enqueue_before(2100, prefix="tmp")
        e1 = enqueue_before(2200, prefix="err")
        q2 = enqueue_before(1000)
        t2 = enqueue_before(1100, prefix="tmp")
        e2 = enqueue_before(1200, prefix="err")

        q.cleanup(1500)
        # old err+tmp files are removed; old queue entries are not.
        expected_unremoved = [q1, q2, t2, e2]
        actual_unremoved = q._queued_files()
        actual_unremoved.extend(q._queued_files("tmp"))
        actual_unremoved.extend(q._queued_files("err"))
        self.assertEquals(expected_unremoved, actual_unremoved)

        # create an invalid file too, just to complicate things.
        invalid = "tmp_invalid.txt"
        os.close(os.open(os.path.join(q.queue_dir, invalid), os.O_CREAT))

        q.cleanup(100)
        expected_unremoved = [q1, q2, invalid]
        actual_unremoved = q._queued_files()
        actual_unremoved.extend(q._queued_files("tmp"))
        actual_unremoved.extend(q._queued_files("err"))
        self.assertEquals(expected_unremoved, actual_unremoved)


if __name__ == '__main__':
    unittest.main()
