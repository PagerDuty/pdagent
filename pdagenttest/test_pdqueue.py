
import os
import shutil
from threading import Lock, Thread
import time
import unittest

from pdagent.constants import \
    EVENT_CONSUMED, EVENT_NOT_CONSUMED, EVENT_BAD_ENTRY,\
    EVENT_BACKOFF_SVCKEY_BAD_ENTRY, EVENT_BACKOFF_SVCKEY_NOT_CONSUMED, \
    EVENT_STOP_ALL
from pdagent.pdqueue import PDQueue, EmptyQueue


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_QUEUE_DIR = os.path.join(_TEST_DIR, "test_queue")
TEST_DB_DIR = os.path.join(_TEST_DIR, "test_db")
BACKOFF_SECS = [1, 2, 4]


class NoOpLock:

    def __init__(self, lockfile):
        pass

    def acquire(self):
        pass

    def release(self):
        pass


class MockBackupDB:

    def __init__(self):
        self._data = None

    def get(self):
        return self._data

    def set(self, json_data):
        self._data = json_data

class MockTime:

    def __init__(self, time_sec=time.time()):
        self._time_sec = time_sec

    def time(self):
        return self._time_sec

    def sleep(self, duration_sec):
        self._time_sec += duration_sec


class PDQueueTest(unittest.TestCase):

    def setUp(self):
        if os.path.exists(TEST_QUEUE_DIR):
            shutil.rmtree(TEST_QUEUE_DIR)
        os.makedirs(TEST_QUEUE_DIR)
        if os.path.exists(TEST_DB_DIR):
            shutil.rmtree(TEST_DB_DIR)
        os.makedirs(TEST_DB_DIR)

    def newQueue(self):
        return PDQueue(
            queue_dir=TEST_QUEUE_DIR,
            lock_class=NoOpLock,
            time_calc=MockTime(),
            backoff_secs=BACKOFF_SECS,
            backoff_db=MockBackupDB())

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

    def test_enqueue_and_dequeue(self):
        q = self.newQueue()

        self.assertEquals(q._queued_files(), [])

        f_foo = q.enqueue("svckey1", "foo")
        self.assertEquals(q._queued_files(), [f_foo])
        self.assertEquals(open(q._abspath(f_foo)).read(), "foo")

        q.time.sleep(0.05)
        f_bar = q.enqueue("svckey2", "bar")  # different service key
        self.assertEquals(q._queued_files(), [f_foo, f_bar])
        self.assertEquals(open(q._abspath(f_foo)).read(), "foo")
        self.assertEquals(open(q._abspath(f_bar)).read(), "bar")

        q.time.sleep(0.05)
        f_baz = q.enqueue("svckey1", "baz")
        self.assertEquals(q._queued_files(), [f_foo, f_bar, f_baz])
        self.assertEquals(open(q._abspath(f_foo)).read(), "foo")
        self.assertEquals(open(q._abspath(f_bar)).read(), "bar")
        self.assertEquals(open(q._abspath(f_baz)).read(), "baz")

        def verify_and_consume(event):
            def consume(s):
                self.assertEquals(event, s)
                return EVENT_CONSUMED
            return consume
        q.dequeue(verify_and_consume("foo"))
        q.dequeue(verify_and_consume("bar"))
        q.dequeue(verify_and_consume("baz"))

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

    def test_backoff_bad_event(self):
        # The item and all other items for same service key must get backed off
        # until backoff limit is hit, then the offending item should get tagged
        # as error, and not be available for further consumption.
        q = self.newQueue()
        q.enqueue("svckey1", "foo")
        q.time.sleep(0.05)
        q.enqueue("svckey1", "bar")
        q.time.sleep(0.05)
        q.enqueue("svckey2", "baz")

        events_processed = []
        count = 0
        # total attempts including backoffs, after which corrective action
        # for bad event kicks in, i.e. kicks in for the max-th attempt.
        max_total_attempts = len(BACKOFF_SECS) + 1

        def consume_with_backoff(s):
            events_processed.append(s)
            if count == 1 and s == "baz":
                # good service key; processed only once.
                return EVENT_CONSUMED
            elif count <= max_total_attempts and s == "foo":
                # while back-off limit is not exceeded for bad event, only first
                # event for service key is processed.
                return EVENT_BACKOFF_SVCKEY_BAD_ENTRY
            elif count == max_total_attempts and s == "bar":
                # when back-off limit has exceeded, bad event is kicked out, and
                # next event is finally processed.
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
        self._assertBackupData(q, [("svckey1", 1, 0)])

        # retry immediately. later-retriable events must not be processed.
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(len(events_processed), 0)
        self.assertEquals(len(q._queued_files()), 2)
        self.assertEquals(len(q._queued_files("err_")), 0)
        self._assertBackupData(q, [("svckey1", 1, 0)])

        # retry just shy of max allowed times.
        for i in range(2, max_total_attempts):
            q.time.sleep(BACKOFF_SECS[i-2])
            count += 1
            events_processed = []
            q.flush(consume_with_backoff)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(len(q._queued_files()), 2)  # 2 from bad svckey
            self.assertEquals(len(q._queued_files("err_")), 0)  # no error yet
            self._assertBackupData(q, [("svckey1", i, i-1)])

        # retry now. there should be no more backoffs, bad event should be
        # kicked out, and next event should finally be processed.
        q.time.sleep(BACKOFF_SECS[len(BACKOFF_SECS)-1])
        count += 1
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(events_processed, ["foo", "bar"])  # bad + next events
        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(len(q._queued_files("err_")), 1)
        self._assertBackupData(q, None)

        # and now, the queue must be empty.
        self.assertRaises(EmptyQueue, q.dequeue, lambda s: EVENT_CONSUMED)

    def test_backoff_not_consumed(self):
        # The item and all other items for same service key must get backed off
        # until backoff limit is hit, then continue getting backed off until the
        # erroneous event is consumed.
        q = self.newQueue()
        q.enqueue("svckey1", "foo")
        q.time.sleep(0.05)
        q.enqueue("svckey1", "bar")
        q.time.sleep(0.05)
        q.enqueue("svckey2", "baz")

        events_processed = []
        count = 0
        # total attempts including backoffs, after which corrective action
        # for bad event kicks in, i.e. kicks in for the max-th attempt.
        max_total_attempts = len(BACKOFF_SECS) + 1

        def consume_with_backoff(s):
            events_processed.append(s)
            if count == 1 and s == "baz":
                # good service key; processed only once.
                return EVENT_CONSUMED
            elif count <= max_total_attempts + 1 and s == "foo":
                # until, and even after, back-off limit has exceeded, bad event
                # is processed. (Next event is processed only when bad event
                # becomes good.)
                return EVENT_BACKOFF_SVCKEY_NOT_CONSUMED
            elif count == max_total_attempts + 2 and s in ["foo", "bar"]:
                # next event finally processed because all events are now good.
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
        self._assertBackupData(q, [("svckey1", 1, 0)])

        # retry immediately. later-retriable events must not be processed.
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(len(events_processed), 0)
        self.assertEquals(len(q._queued_files()), 2)
        self.assertEquals(len(q._queued_files("err_")), 0)
        self._assertBackupData(q, [("svckey1", 1, 0)])

        # retry just shy of max allowed times.
        for i in range(2, max_total_attempts):
            q.time.sleep(BACKOFF_SECS[i-2])
            count += 1
            events_processed = []
            q.flush(consume_with_backoff)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(len(q._queued_files()), 2)  # 2 from bad svckey
            self.assertEquals(len(q._queued_files("err_")), 0)  # no error yet
            self._assertBackupData(q, [("svckey1", i, i-1)])

        # try a couple more times (we exceed max attempts going forward) --
        # bad event is still processed.
        latest_backoff_sec_index = len(BACKOFF_SECS)-1
        for i in [0, 1]:
            q.time.sleep(BACKOFF_SECS[len(BACKOFF_SECS)-1])
            count += 1
            events_processed = []
            q.flush(consume_with_backoff)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(len(q._queued_files()), 2)  # 2 from bad svckey
            self.assertEquals(len(q._queued_files("err_")), 0)  # still no errors
            self._assertBackupData(q,
                [("svckey1", max_total_attempts + i, latest_backoff_sec_index)]
            )

        # retry now (much after max_backoff_attempts), with no bad event.
        q.time.sleep(BACKOFF_SECS[latest_backoff_sec_index])
        count += 1
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(events_processed, ["foo", "bar"])  # all good events
        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(len(q._queued_files("err_")), 0)   # no errors
        self._assertBackupData(q, None)

        # and now, the queue must be empty.
        self.assertRaises(EmptyQueue, q.dequeue, lambda s: EVENT_CONSUMED)

    def test_stop_processing(self):
        # No later event must be processed.
        q = self.newQueue()
        q.enqueue("svckey1", "foo")
        q.time.sleep(1)
        q.enqueue("svckey1", "bar")
        q.time.sleep(1)
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
        time.sleep(0.1)  # [real sleep] give thread time to acquire lock & sleep

        self.assertEquals(trace, ["Li", "La", "C1"])
        self.assertEquals(q._queued_files(), [f_foo])

        f_bar = q.enqueue("svckey", "bar")

        self.assertEquals(trace, ["Li", "La", "C1"])
        self.assertEquals(q._queued_files(), [f_foo, f_bar])

        time.sleep(0.2)  # [real sleep]

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

    def test_resurrect(self):
        q = self.newQueue()
        fnames = []
        errnames = []
        fnames.append(q.enqueue("svckey1", "foo"))
        fnames.append(q.enqueue("svckey1", "bar"))
        fnames.append(q.enqueue("svckey2", "baz"))
        fnames.append(q.enqueue("svckey2", "boo"))
        fnames.append(q.enqueue("svckey3", "bam"))
        q._tag_as_error(fnames[0])
        q._tag_as_error(fnames[2])
        q._tag_as_error(fnames[4])

        self.assertEquals(len(q._queued_files()), 2)
        self.assertEquals(len(q._queued_files("err_")), 3)

        q.resurrect("svckey1")
        self.assertEquals(len(q._queued_files()), 3)
        errfiles = q._queued_files("err_")
        self.assertEquals(len(errfiles), 2)
        for errname in errfiles:
            self.assertEquals(errname.find("svckey1"), -1)
            self.assertTrue(errname.find("svckey2") == -1 or \
                errname.find("svckey3") == -1)

        q.resurrect()
        self.assertEquals(len(q._queued_files()), 5)
        self.assertEquals(len(q._queued_files("err_")), 0)

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

    def _assertBackupData(self, q, data):
        backup_data = q.backoff_db.get()
        attempts = {}
        retries = {}

        if data:
            for (svc_key, count, backoff_index) in data:
                attempts[svc_key] = count
                retries[svc_key] = int(
                    q.time.time() + BACKOFF_SECS[backoff_index])

        self.assertDictEqual(backup_data, {
            "attempts": attempts,
            "next_retries": retries
        })



if __name__ == '__main__':
    unittest.main()
