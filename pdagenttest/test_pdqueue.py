
import os
import shutil
from threading import Lock, Thread
import time
import unittest

from pdagent.constants import ConsumeEvent
from pdagent.pdqueue import PDQueue, EmptyQueueError


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
            max_event_bytes=10,
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
                return ConsumeEvent.CONSUMED
            return consume
        q.dequeue(verify_and_consume("foo"))
        q.dequeue(verify_and_consume("bar"))
        q.dequeue(verify_and_consume("baz"))

        # check queue is empty
        self.assertEquals(q._queued_files(), [])
        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s: ConsumeEvent.CONSUMED)

        # verify that queued files are now success files.
        success_contents = [
            open(q._abspath(f)).read()
            for f in q._queued_files("suc")
        ]
        self.assertEquals(success_contents, ["foo", "bar", "baz"])

    def test_dont_consume(self):
        # The item should stay in the queue if we don't consume it.
        q = self.newQueue()
        q.enqueue("svckey", "foo")

        def dont_consume_foo(s):
            self.assertEquals("foo", s)
            return ConsumeEvent.NOT_CONSUMED
        q.dequeue(dont_consume_foo)
        q.dequeue(dont_consume_foo)

        def consume_foo(s):
            self.assertEquals("foo", s)
            return ConsumeEvent.CONSUMED
        q.dequeue(consume_foo)

        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s: ConsumeEvent.CONSUMED)

    def test_consume_error(self):
        # The item should get tagged as error, and not be available for
        # further consumption, if consumption causes error.
        q = self.newQueue()
        q.enqueue("svckey", "foo")

        def erroneous_consume_foo(s):
            self.assertEquals("foo", s)
            return ConsumeEvent.BAD_ENTRY
        q.dequeue(erroneous_consume_foo)

        self.assertEquals(len(q._queued_files("err_")), 1)
        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s: ConsumeEvent.CONSUMED)

    def test_huge_event_not_processed(self):
        # The item should get tagged as error, and not be available for
        # further consumption.
        q = self.newQueue()
        f = q.enqueue("svckey", "huuuuuuuuge")
        self.assertEquals(q._queued_files(), [f])

        def unexpected_consume(s):
            self.fail("Unexpected event %s" % s)
        q.dequeue(unexpected_consume)  # consume function must not be called.

        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(len(q._queued_files("err_")), 1)

    def test_backoff_bad_event(self):
        # The item and all other items for same service key must get backed off
        # until backoff limit is hit, then the offending item should get tagged
        # as error, and not be available for further consumption.
        q = self.newQueue()
        e1_1 = q.enqueue("svckey1", "foo")
        q.time.sleep(0.05)
        e1_2 = q.enqueue("svckey1", "bar")
        q.time.sleep(0.05)
        e2_1 = q.enqueue("svckey2", "baz")

        events_processed = []
        count = 0
        # total attempts including backoffs, after which corrective action
        # for bad event kicks in, i.e. kicks in for the max-th attempt.
        max_total_attempts = len(BACKOFF_SECS) + 1

        def consume_with_backoff(s):
            events_processed.append(s)
            if count == 1 and s == "baz":
                # good service key; processed only once.
                return ConsumeEvent.CONSUMED
            elif count <= max_total_attempts and s == "foo":
                # while back-off limit is not exceeded for bad event, only first
                # event for service key is processed.
                return ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY
            elif count == max_total_attempts and s == "bar":
                # when back-off limit has exceeded, bad event is kicked out, and
                # next event is finally processed.
                return ConsumeEvent.CONSUMED
            else:
                self.fail(
                    "Unexpected event %s in attempt %d" % (s, count))

        self.assertEquals(q._queued_files(), [e1_1, e1_2, e2_1])

        # flush once.
        count += 1
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(events_processed, ["foo", "baz"])  # 1 bad, 1 good
        self.assertEquals(q._queued_files(), [e1_1, e1_2])  # 2 from bad svckey
        self.assertEquals(len(q._queued_files("err_")), 0)  # no error yet.
        self._assertBackoffData(q, [("svckey1", 1, 0)])

        # retry immediately. later-retriable events must not be processed.
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(len(events_processed), 0)
        self.assertEquals(q._queued_files(), [e1_1, e1_2])
        self.assertEquals(len(q._queued_files("err_")), 0)
        self._assertBackoffData(q, [("svckey1", 1, 0)])

        # retry just shy of max allowed times.
        for i in range(2, max_total_attempts):
            q.time.sleep(BACKOFF_SECS[i-2])
            count += 1
            events_processed = []
            q.flush(consume_with_backoff)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(q._queued_files(), [e1_1, e1_2])  # bad svckey's
            self.assertEquals(len(q._queued_files("err_")), 0)  # no error yet
            self._assertBackoffData(q, [("svckey1", i, i-1)])

        # retry now. there should be no more backoffs, bad event should be
        # kicked out, and next event should finally be processed.
        q.time.sleep(BACKOFF_SECS[-1])
        count += 1
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(events_processed, ["foo", "bar"])  # bad + next events
        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(q._queued_files("err_"),
            [e1_1.replace("pdq_", "err_")])
        self._assertBackoffData(q, None)

        # and now, the queue must be empty.
        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s: ConsumeEvent.CONSUMED)

    def test_backoff_not_consumed(self):
        # The item and all other items for same service key must get backed off
        # until backoff limit is hit, then continue getting backed off until the
        # erroneous event is consumed.
        q = self.newQueue()
        e1_1 = q.enqueue("svckey1", "foo")
        q.time.sleep(0.05)
        e1_2 = q.enqueue("svckey1", "bar")
        q.time.sleep(0.05)
        e2_1 = q.enqueue("svckey2", "baz")

        events_processed = []
        count = 0
        # total attempts including backoffs, after which corrective action
        # for bad event kicks in, i.e. kicks in for the max-th attempt.
        max_total_attempts = len(BACKOFF_SECS) + 1

        def consume_with_backoff(s):
            events_processed.append(s)
            if count == 1 and s == "baz":
                # good service key; processed only once.
                return ConsumeEvent.CONSUMED
            elif count <= max_total_attempts + 1 and s == "foo":
                # until, and even after, back-off limit has exceeded, bad event
                # is processed. (Next event is processed only when bad event
                # becomes good.)
                return ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED
            elif count == max_total_attempts + 2 and s in ["foo", "bar"]:
                # next event finally processed because all events are now good.
                return ConsumeEvent.CONSUMED
            else:
                self.fail(
                    "Unexpected event %s in attempt %d" % (s, count))

        self.assertEquals(q._queued_files(), [e1_1, e1_2, e2_1])

        # flush once.
        count += 1
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(events_processed, ["foo", "baz"])  # 1 bad, 1 good
        self.assertEquals(q._queued_files(), [e1_1, e1_2])  # 2 from bad svckey
        self.assertEquals(len(q._queued_files("err_")), 0)  # no error yet.
        self._assertBackoffData(q, [("svckey1", 1, 0)])

        # retry immediately. later-retriable events must not be processed.
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(len(events_processed), 0)
        self.assertEquals(q._queued_files(), [e1_1, e1_2])
        self.assertEquals(len(q._queued_files("err_")), 0)
        self._assertBackoffData(q, [("svckey1", 1, 0)])

        # retry just shy of max allowed times.
        for i in range(2, max_total_attempts):
            q.time.sleep(BACKOFF_SECS[i-2])
            count += 1
            events_processed = []
            q.flush(consume_with_backoff)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(q._queued_files(), [e1_1, e1_2])  # bad svckey's
            self.assertEquals(len(q._queued_files("err_")), 0)  # no error yet
            self._assertBackoffData(q, [("svckey1", i, i-1)])

        # try a couple more times (we exceed max attempts going forward) --
        # bad event is still processed.
        for i in [0, 1]:
            q.time.sleep(BACKOFF_SECS[-1])
            count += 1
            events_processed = []
            q.flush(consume_with_backoff)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(q._queued_files(), [e1_1, e1_2])  # bad svckey's
            self.assertEquals(len(q._queued_files("err_")), 0)  # still no errors
            self._assertBackoffData(q,
                [("svckey1", max_total_attempts + i, -1)]
            )

        # retry now (much after max_backoff_attempts), with no bad event.
        q.time.sleep(BACKOFF_SECS[-1])
        count += 1
        events_processed = []
        q.flush(consume_with_backoff)
        self.assertEquals(events_processed, ["foo", "bar"])  # all good events
        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(len(q._queued_files("err_")), 0)   # no errors
        self._assertBackoffData(q, None)

        # and now, the queue must be empty.
        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s: ConsumeEvent.CONSUMED)

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
                return ConsumeEvent.STOP_ALL
            elif count == 2:
                # next time, we'll consider it a success.
                return ConsumeEvent.CONSUMED
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
        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s: ConsumeEvent.CONSUMED)

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
                    return ConsumeEvent.CONSUMED
                q.dequeue(consume)
            except EmptyQueueError:
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
            except EmptyQueueError:
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
            return ConsumeEvent.CONSUMED

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
        fnames.append(q.enqueue("svckey1", "foo"))
        fnames.append(q.enqueue("svckey1", "bar"))
        fnames.append(q.enqueue("svckey2", "baz"))
        fnames.append(q.enqueue("svckey2", "boo"))
        fnames.append(q.enqueue("svckey3", "bam"))
        q._unsafe_change_event_type(fnames[0], "pdq_", "err_")
        q._unsafe_change_event_type(fnames[2], "pdq_", "err_")
        q._unsafe_change_event_type(fnames[4], "pdq_", "err_")

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

        q.resurrect("non_existent_key")  # should not throw an error.

        q.resurrect()
        self.assertEquals(len(q._queued_files()), 5)
        self.assertEquals(len(q._queued_files("err_")), 0)

    def test_status(self):
        q = self.newQueue()
        fnames = []
        fnames.append(q.enqueue("svckey1", "e11"))
        fnames.append(q.enqueue("svckey1", "e12"))
        fnames.append(q.enqueue("svckey1", "e13"))
        fnames.append(q.enqueue("svckey2", "e21"))
        fnames.append(q.enqueue("svckey2", "e22"))
        fnames.append(q.enqueue("svckey3", "e31"))
        fnames.append(q.enqueue("svckey3", "e32"))
        fnames.append(q.enqueue("svckey4", "e41"))
        fnames.append(q.enqueue("svckey4", "e42"))
        q._unsafe_change_event_type(fnames[0], "pdq_", "err_")
        q._unsafe_change_event_type(fnames[2], "pdq_", "suc_")
        q._unsafe_change_event_type(fnames[3], "pdq_", "err_")
        q._unsafe_change_event_type(fnames[4], "pdq_", "err_")
        q._unsafe_change_event_type(fnames[7], "pdq_", "suc_")
        q._unsafe_change_event_type(fnames[8], "pdq_", "suc_")

        q.backoff_info.increment("svckey2")

        self.assertEqual(q.get_status("svckey1"), {
            "service_keys": 1,
            "events": {
                "svckey1": {
                    "pending": 1,
                    "error": 1,
                    "success": 1
                }
            }
        })

        self.assertEqual(q.get_status("non_existent_key"), {
            "service_keys": 0,
            "events": {}
        })

        expected_stats = {
            "service_keys": 4,
            "events": {
                "svckey1": {
                    "pending": 1, "success": 1, "error": 1
                },
                "svckey2": {
                    "pending": 0, "success": 0, "error": 2
                },
                "svckey3": {
                    "pending": 2, "success": 0, "error": 0
                },
                "svckey4": {
                    "pending": 0, "success": 2, "error": 0
                }
            }
        }
        self.assertEqual(q.get_status(), expected_stats)

        expected_stats["throttled_keys"] = 1
        self.assertEqual(q.get_status(throttle_info=True), expected_stats)

        expected_aggr_stats = {
            "service_keys": 4,
            "events": {
                "pending": 3,
                "success": 3,
                "error": 3
            }
        }
        self.assertEqual(q.get_status(aggregated=True), expected_aggr_stats)

        expected_aggr_stats["throttled_keys"] = 1
        self.assertEqual(
            q.get_status(throttle_info=True, aggregated=True),
            expected_aggr_stats
        )

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
        s2 = enqueue_before(2300, prefix="suc")
        q2 = enqueue_before(1000)
        t2 = enqueue_before(1100, prefix="tmp")
        s2 = enqueue_before(1150, prefix="suc")
        e2 = enqueue_before(1200, prefix="err")

        q.cleanup(1500)
        # old err+tmp+suc files are removed; old queue entries are not.
        expected_unremoved = [q1, q2, t2, e2, s2]
        actual_unremoved = q._queued_files()
        actual_unremoved.extend(q._queued_files("tmp"))
        actual_unremoved.extend(q._queued_files("err"))
        actual_unremoved.extend(q._queued_files("suc"))
        self.assertEquals(expected_unremoved, actual_unremoved)

        # create an invalid file too, just to complicate things.
        invalid = "tmp_invalid.txt"
        os.close(os.open(os.path.join(q.queue_dir, invalid), os.O_CREAT))

        q.cleanup(100)
        expected_unremoved = [q1, q2, invalid]
        actual_unremoved = q._queued_files()
        actual_unremoved.extend(q._queued_files("tmp"))
        actual_unremoved.extend(q._queued_files("err"))
        actual_unremoved.extend(q._queued_files("suc"))
        self.assertEquals(expected_unremoved, actual_unremoved)

    def _assertBackoffData(self, q, data):
        backup_data = q.backoff_info._db.get()
        attempts = {}
        retries = {}

        if data:
            for (svc_key, count, backoff_index) in data:
                attempts[svc_key] = count
                retries[svc_key] = int(
                    q.time.time() + BACKOFF_SECS[backoff_index])

        self.assertEqual(backup_data, {
            "attempts": attempts,
            "next_retries": retries
        })



if __name__ == '__main__':
    unittest.main()
