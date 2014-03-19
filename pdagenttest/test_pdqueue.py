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

import os
import shutil
from threading import Lock, Thread
import time
import unittest

from pdagent.constants import ConsumeEvent
from pdagent.pdqueue import PDQEnqueuer, PDQueue, EmptyQueueError


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_QUEUE_DIR = os.path.join(_TEST_DIR, "test_queue")
TEST_DB_DIR = os.path.join(_TEST_DIR, "test_db")
BACKOFF_INTERVALS = [1, 2, 4]


class NoOpLock:

    def __init__(self, lockfile):
        pass

    def acquire(self):
        pass

    def release(self):
        pass


class MockDB:

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

    def gmtime(self):
        return "some_utc_time"

    def strftime(self, fmt, t):
        if fmt == "%Y-%m-%dT%H:%M:%SZ":
            return t
        else:
            raise Exception("Expected format-string in ISO format, got " + fmt)


class PDQueueTest(unittest.TestCase):

    def setUp(self):
        if os.path.exists(TEST_QUEUE_DIR):
            shutil.rmtree(TEST_QUEUE_DIR)
        os.makedirs(TEST_QUEUE_DIR)
        if os.path.exists(TEST_DB_DIR):
            shutil.rmtree(TEST_DB_DIR)
        os.makedirs(TEST_DB_DIR)

    def new_queue(self):
        mock_time = MockTime()
        eq = PDQEnqueuer(
            queue_dir=TEST_QUEUE_DIR,
            lock_class=NoOpLock,
            time_calc=mock_time,
            enqueue_file_mode=0644,
            )
        q = PDQueue(
            queue_dir=TEST_QUEUE_DIR,
            lock_class=NoOpLock,
            time_calc=mock_time,
            event_size_max_bytes=10,
            backoff_intervals=BACKOFF_INTERVALS,
            backoff_db=MockDB(),
            counter_db=MockDB()
            )
        return eq, q

    def test__open_creat_excl_with_retry(self):
        from pdagent.pdqueue import _open_creat_excl
        eq, _ = self.new_queue()
        fname_abs = eq._abspath("_open_creat_excl_with_retry.txt")
        fd1 = _open_creat_excl(fname_abs, 0644)
        self.assertNotEquals(fd1, None)
        fd2 = None
        try:
            fd2 = _open_creat_excl(fname_abs, 0644)
            self.assertEquals(fd2, None)
        finally:
            os.close(fd1)
            if fd2:
                os.close(fd2)

    def test_enqueue_and_dequeue(self):
        eq, q = self.new_queue()

        self.assertEquals(q._queued_files(), [])

        f_foo = eq.enqueue("svckey1", "foo")
        self.assertEquals(q._queued_files(), [f_foo])
        self.assertEquals(open(q._abspath(f_foo)).read(), "foo")

        q.time.sleep(0.05)
        f_bar = eq.enqueue("svckey2", "bar")  # different service key
        self.assertEquals(q._queued_files(), [f_foo, f_bar])
        self.assertEquals(open(q._abspath(f_foo)).read(), "foo")
        self.assertEquals(open(q._abspath(f_bar)).read(), "bar")

        q.time.sleep(0.05)
        f_baz = eq.enqueue("svckey1", "baz")
        self.assertEquals(q._queued_files(), [f_foo, f_bar, f_baz])
        self.assertEquals(open(q._abspath(f_foo)).read(), "foo")
        self.assertEquals(open(q._abspath(f_bar)).read(), "bar")
        self.assertEquals(open(q._abspath(f_baz)).read(), "baz")

        def verify_and_consume(event, event_id):
            def consume(s, i):
                self.assertEquals(event, s)
                self.assertEquals(event_id, i)
                return ConsumeEvent.CONSUMED
            return consume
        q.dequeue(verify_and_consume("foo", f_foo))
        q.dequeue(verify_and_consume("bar", f_bar))
        q.dequeue(verify_and_consume("baz", f_baz))

        # check queue is empty
        self.assertEquals(q._queued_files(), [])
        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s, i: ConsumeEvent.CONSUMED
            )

        # verify that queued files are now success files.
        success_contents = []
        for f in q._queued_files("suc"):
            fd = open(q._abspath(f))
            success_contents.append(fd.read())
            fd.close()
        self.assertEquals(success_contents, ["foo", "bar", "baz"])

    def test_consume_error(self):
        # The item should get tagged as error, and not be available for
        # further consumption, if consumption causes error.
        eq, q = self.new_queue()
        f_foo = eq.enqueue("svckey", "foo")

        def erroneous_consume_foo(s, i):
            self.assertEquals("foo", s)
            self.assertEquals(f_foo, i)
            return ConsumeEvent.BAD_ENTRY
        q.dequeue(erroneous_consume_foo)

        self.assertEquals(len(q._queued_files("err_")), 1)
        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s: ConsumeEvent.CONSUMED
            )

    def test_huge_event_not_processed(self):
        # The item should get tagged as error, and not be available for
        # further consumption.
        eq, q = self.new_queue()
        f = eq.enqueue("svckey", "huuuuuuuuge")
        self.assertEquals(q._queued_files(), [f])

        def unexpected_consume(s, i):
            self.fail("Unexpected event %s" % s)
        q.dequeue(unexpected_consume)  # consume function must not be called.

        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(len(q._queued_files("err_")), 1)
        self._assertCounterData(q, (0, 1))

    def test_backoff_bad_event(self):
        # The item and all other items for same service key must get backed off
        # until backoff limit is hit, then the offending item should get tagged
        # as error, and not be available for further consumption.
        eq, q = self.new_queue()
        e1_1 = eq.enqueue("svckey1", "foo")
        q.time.sleep(0.05)
        e1_2 = eq.enqueue("svckey1", "bar")
        q.time.sleep(0.05)
        e2_1 = eq.enqueue("svckey2", "baz")

        events_processed = []
        count = 0
        # total attempts including backoffs, after which corrective action
        # for bad event kicks in, i.e. kicks in for the max-th attempt.
        max_total_attempts = len(BACKOFF_INTERVALS) + 1

        def consume_with_backoff(s, i):
            events_processed.append(s)
            if count == 1 and s == "baz" and i == e2_1:
                # good service key; processed only once.
                return ConsumeEvent.CONSUMED
            elif count <= max_total_attempts and s == "foo" and i == e1_1:
                # while back-off limit is not exceeded for bad event, only first
                # event for service key is processed.
                return ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY
            elif count == max_total_attempts and s == "bar" and i == e1_2:
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
        q.flush(consume_with_backoff, lambda: False)
        self.assertEquals(events_processed, ["foo", "baz"])  # 1 bad, 1 good
        self.assertEquals(q._queued_files(), [e1_1, e1_2])  # 2 from bad svckey
        self.assertEquals(len(q._queued_files("err_")), 0)  # no error yet.
        self._assertBackoffData(q, [("svckey1", 1, 0)])
        self._assertCounterData(q, (1, 0))

        # retry immediately. later-retriable events must not be processed.
        events_processed = []
        q.flush(consume_with_backoff, lambda: False)
        self.assertEquals(len(events_processed), 0)
        self.assertEquals(q._queued_files(), [e1_1, e1_2])
        self.assertEquals(len(q._queued_files("err_")), 0)
        self._assertBackoffData(q, [("svckey1", 1, 0)])
        self._assertCounterData(q, (1, 0))

        # retry just shy of max allowed times.
        for i in range(2, max_total_attempts):
            q.time.sleep(BACKOFF_INTERVALS[i-2])
            count += 1
            events_processed = []
            q.flush(consume_with_backoff, lambda: False)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(q._queued_files(), [e1_1, e1_2])  # bad svckey's
            self.assertEquals(len(q._queued_files("err_")), 0)  # no error yet
            self._assertBackoffData(q, [("svckey1", i, i-1)])
            self._assertCounterData(q, (1, 0))

        # retry now. there should be no more backoffs, bad event should be
        # kicked out, and next event should finally be processed.
        q.time.sleep(BACKOFF_INTERVALS[-1])
        count += 1
        events_processed = []
        q.flush(consume_with_backoff, lambda: False)
        self.assertEquals(events_processed, ["foo", "bar"])  # bad + next events
        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(
            q._queued_files("err_"),
            [e1_1.replace("pdq_", "err_")]
            )
        self._assertBackoffData(q, None)
        self._assertCounterData(q, (2, 1))

        # and now, the queue must be empty.
        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s, i: ConsumeEvent.CONSUMED
            )
        self._assertCounterData(q, (2, 1))

    def test_backoff_not_consumed(self):
        # The item and all other items for same service key must get backed off
        # until backoff limit is hit, then continue getting backed off until the
        # erroneous event is consumed.
        eq, q = self.new_queue()
        e1_1 = eq.enqueue("svckey1", "foo")
        q.time.sleep(0.05)
        e1_2 = eq.enqueue("svckey1", "bar")
        q.time.sleep(0.05)
        e2_1 = eq.enqueue("svckey2", "baz")

        events_processed = []
        count = 0
        # total attempts including backoffs, after which corrective action
        # for bad event kicks in, i.e. kicks in for the max-th attempt.
        max_total_attempts = len(BACKOFF_INTERVALS) + 1

        def consume_with_backoff(s, i):
            events_processed.append(s)
            if count == 1 and s == "baz":
                # good service key; processed only once.
                return ConsumeEvent.CONSUMED
            elif count <= max_total_attempts + 1 and s == "foo" and i == e1_1:
                # until, and even after, back-off limit has exceeded, bad event
                # is processed. (Next event is processed only when bad event
                # becomes good.)
                return ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED
            elif count == max_total_attempts + 2 and \
                    ((s == "foo" and i == e1_1) or s == "bar" and i == e1_2):
                # next event finally processed because all events are now good.
                return ConsumeEvent.CONSUMED
            else:
                self.fail("Unexpected event %s in attempt %d" % (s, count))

        self.assertEquals(q._queued_files(), [e1_1, e1_2, e2_1])

        # flush once.
        count += 1
        events_processed = []
        q.flush(consume_with_backoff, lambda: False)
        self.assertEquals(events_processed, ["foo", "baz"])  # 1 bad, 1 good
        self.assertEquals(q._queued_files(), [e1_1, e1_2])  # 2 from bad svckey
        self.assertEquals(len(q._queued_files("err_")), 0)  # no error yet.
        self._assertBackoffData(q, [("svckey1", 1, 0)])
        self._assertCounterData(q, (1, 0))

        # retry immediately. later-retriable events must not be processed.
        events_processed = []
        q.flush(consume_with_backoff, lambda: False)
        self.assertEquals(len(events_processed), 0)
        self.assertEquals(q._queued_files(), [e1_1, e1_2])
        self.assertEquals(len(q._queued_files("err_")), 0)
        self._assertBackoffData(q, [("svckey1", 1, 0)])
        self._assertCounterData(q, (1, 0))

        # retry just shy of max allowed times.
        for i in range(2, max_total_attempts):
            q.time.sleep(BACKOFF_INTERVALS[i-2])
            count += 1
            events_processed = []
            q.flush(consume_with_backoff, lambda: False)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(q._queued_files(), [e1_1, e1_2])  # bad svckey's
            self.assertEquals(len(q._queued_files("err_")), 0)  # no error yet
            self._assertBackoffData(q, [("svckey1", i, i-1)])
            self._assertCounterData(q, (1, 0))

        # try a couple more times (we exceed max attempts going forward) --
        # bad event is still processed.
        for i in [0, 1]:
            q.time.sleep(BACKOFF_INTERVALS[-1])
            count += 1
            events_processed = []
            q.flush(consume_with_backoff, lambda: False)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(q._queued_files(), [e1_1, e1_2])  # bad svckey's
            self.assertEquals(len(q._queued_files("err_")), 0)  # still no errors
            self._assertBackoffData(
                q,
                [("svckey1", max_total_attempts + i, -1)]
                )
            self._assertCounterData(q, (1, 0))

        # retry now (much after max_backoff_attempts), with no bad event.
        q.time.sleep(BACKOFF_INTERVALS[-1])
        count += 1
        events_processed = []
        q.flush(consume_with_backoff, lambda: False)
        self.assertEquals(events_processed, ["foo", "bar"])  # all good events
        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(len(q._queued_files("err_")), 0)   # no errors
        self._assertBackoffData(q, None)
        self._assertCounterData(q, (3, 0))

        # and now, the queue must be empty.
        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s: ConsumeEvent.CONSUMED
            )
        self._assertCounterData(q, (3, 0))

    def test_stop_processing(self):
        # No later event must be processed.
        eq, q = self.new_queue()
        f_foo = eq.enqueue("svckey1", "foo")
        q.time.sleep(1)
        eq.enqueue("svckey1", "bar")
        q.time.sleep(1)
        eq.enqueue("svckey2", "baz")

        events_processed = []
        count = 0

        def consume_with_stopall(s, i):
            events_processed.append(s)
            if count == 1 and s == "foo" and i == f_foo:
                # first time, we'll ask that no further events be processed.
                return ConsumeEvent.STOP_ALL
            elif count == 2:
                # next time, we'll consider it a success.
                return ConsumeEvent.CONSUMED
            else:
                self.fail("Unexpected event %s in attempt %d" % (s, count))

        self.assertEquals(len(q._queued_files()), 3)

        # flush once. later events must not be processed.
        count += 1
        events_processed = []
        q.flush(consume_with_stopall, lambda: False)
        self.assertEquals(events_processed, ["foo"])
        self.assertEquals(len(q._queued_files()), 3)  # 2 from bad svckey
        self.assertEquals(len(q._queued_files("err_")), 0)  # no error events
        self._assertCounterData(q, (0, 0))

        # retry. all events must now be processed.
        count += 1
        events_processed = []
        q.flush(consume_with_stopall, lambda: False)
        self.assertEquals(events_processed, ["foo", "bar", "baz"])
        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(len(q._queued_files("err_")), 0)  # no error events
        self._assertCounterData(q, (3, 0))

        # and now, the queue must be empty.
        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s: ConsumeEvent.CONSUMED
            )

    def test_enqueue_never_blocks(self):
        # test that a read lock during dequeue does not block an enqueue
        eq, q = self.new_queue()
        f_foo = eq.enqueue("svckey", "foo")

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
                def consume(*args):
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

        f_bar = eq.enqueue("svckey", "bar")

        self.assertEquals(trace, ["Li", "La", "C1"])
        self.assertEquals(q._queued_files(), [f_foo, f_bar])

        time.sleep(0.2)  # [real sleep]

        self.assertEquals(trace, ["Li", "La", "C1", "C2", "Lr"])
        self.assertEquals(q._queued_files(), [f_bar])

    def test_parallel_dequeue(self):
        # test that a dequeue blocks another dequeue using locking

        eq1, q1 = self.new_queue()
        _, q2 = self.new_queue()
        eq1.enqueue("svckey", "foo")

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
                def consume2(*args):
                    self.fail()  # consume2 shouldn't be called!
                q2.dequeue(consume2)
            except EmptyQueueError:
                trace.append("q2_EQ")

        thread_dequeue2 = Thread(target=dequeue2)

        def consume1(s, i):
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
        eq, q = self.new_queue()
        fnames = []
        fnames.append(eq.enqueue("svckey1", "foo"))
        fnames.append(eq.enqueue("svckey1", "bar"))
        fnames.append(eq.enqueue("svckey2", "baz"))
        fnames.append(eq.enqueue("svckey2", "boo"))
        fnames.append(eq.enqueue("svckey3", "bam"))
        for i in [0, 2, 4]:
            q._unsafe_change_event_type(fnames[i], "pdq_", "err_")

        self.assertEquals(len(q._queued_files()), 2)
        self.assertEquals(len(q._queued_files("err_")), 3)

        q.resurrect("svckey1")
        self.assertEquals(len(q._queued_files()), 3)
        errfiles = q._queued_files("err_")
        self.assertEquals(len(errfiles), 2)
        for errname in errfiles:
            self.assertEquals(errname.find("svckey1"), -1)
            self.assertTrue(
                errname.find("svckey2") != -1 or
                errname.find("svckey3") != -1
                )

        q.resurrect("non_existent_key")  # should not throw an error.

        q.resurrect()
        self.assertEquals(len(q._queued_files()), 5)
        self.assertEquals(len(q._queued_files("err_")), 0)

        # counters should not be touched.
        self._assertCounterData(q, None)

    def test_stats(self):
        eq, q = self.new_queue()
        events = ["e11", "e12", "e13", "e21", "e22", "e31", "e32", "e41", "e42"]
        fnames = []
        for e in events:
            # events are in the form e<svckey#><event#>
            k = e[1]
            fnames.append(eq.enqueue("svckey%s" % k, e))
            eq.time.sleep(5)

        # 1 error for svckey1; 2 for svckey2
        for i in [0, 3, 4]:
            q._unsafe_change_event_type(fnames[i], "pdq_", "err_")
        # 1 success for svckey1; 2 for svckey4
        for i in [2, 7, 8]:
            q._unsafe_change_event_type(fnames[i], "pdq_", "suc_")
        # that leaves 1 pending for svckey1; 2 for svckey3

        # also, let's throttle svckey2...
        q.backoff_info.increment("svckey2")
        # ... and increment some counters.
        for _ in range(20):
            q.counter_info.increment_success()
        for _ in range(2):
            q.counter_info.increment_failure()

        expected_stats = {
            "snapshot": {
                "pending_events": {
                    "count": 3,
                    "newest_age_secs": 15,
                    "oldest_age_secs": 40,
                    "service_keys_count": 2
                    },
                "succeeded_events": {
                    "count": 3,
                    "newest_age_secs": 5,
                    "oldest_age_secs": 35,
                    "service_keys_count": 2
                    },
                "failed_events": {
                    "count": 3,
                    "newest_age_secs": 25,
                    "oldest_age_secs": 45,
                    "service_keys_count": 2
                    },
                "throttled_service_keys_count": 1
                },
            "aggregate": {
                "successful_events_count": 20,
                "failed_events_count": 2,
                "started_on": "some_utc_time"
                }
            }
        self.assertEqual(q.get_stats(detailed_snapshot=True), expected_stats)

        expected_stats["snapshot"].pop("succeeded_events")
        expected_stats["snapshot"].pop("failed_events")
        self.assertEqual(q.get_stats(), expected_stats)

    def test_cleanup(self):
        # simulate enqueues done a while ago.
        eq, q = self.new_queue()

        def enqueue_before(sec, prefix="pdq"):
            enqueue_time_ms = (int(time.time()) - sec) * 1000
            fname = "%s_%d_%s.txt" % (
                prefix,
                enqueue_time_ms,
                "svckey%d" % (enqueue_time_ms % 10)
                )
            fpath = os.path.join(q.queue_dir, fname)
            os.close(os.open(fpath, os.O_CREAT))
            return fname

        # we'll first remove things enqueued >1500s ago, and then <1500s ago.
        q1 = enqueue_before(2000)
        t1 = enqueue_before(2100, prefix="tmp")
        e1 = enqueue_before(2200, prefix="err")
        s1_1 = enqueue_before(2250, prefix="suc")
        s1_2 = enqueue_before(2300, prefix="suc")
        q2 = enqueue_before(1000)
        t2 = enqueue_before(1100, prefix="tmp")
        s2 = enqueue_before(1150, prefix="suc")
        e2_1 = enqueue_before(1200, prefix="err")
        e2_2 = enqueue_before(1250, prefix="err")

        q.cleanup(1500)
        # old err+tmp+suc files are removed; old queue entries are not.
        expected_unremoved = [q1, q2, t2, e2_2, e2_1, s2]
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

        # counters should not be touched.
        self._assertCounterData(q, None)


    def _assertBackoffData(self, q, data):
        backup_data = q.backoff_info._db.get()
        attempts = {}
        retries = {}

        if data:
            for (svc_key, count, backoff_index) in data:
                attempts[svc_key] = count
                retries[svc_key] = int(
                    q.time.time() + BACKOFF_INTERVALS[backoff_index])

        self.assertEqual(backup_data, {
            "attempts": attempts,
            "next_retries": retries
            })


    def _assertCounterData(self, q, data):
        counter_db = q.counter_info._db
        counter_data = counter_db.get()
        expected = None

        if data:
            success, failure = data
            expected = dict()
            if success != 0:
                expected["successful_events_count"] = success
            if failure != 0:
                expected["failed_events_count"] = failure
            try:
                counter_db.cached_valid_since
            except AttributeError:
                # "started_on" must be generated if not present already.
                self.assertNotEquals(counter_data["started_on"], None)
                counter_db.cached_started_on = counter_data["started_on"]
            # "started_on" must not change once generated.
            expected["started_on"] = counter_db.cached_started_on

        self.assertEqual(counter_data, expected)



if __name__ == '__main__':
    unittest.main()
