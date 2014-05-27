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
import stat
from threading import Lock, Thread
import time
import unittest

from pdagent.constants import ConsumeEvent, EnqueueWarnings
from pdagent.pdqueue import PDQEnqueuer, PDQueue, EmptyQueueError
from pdagent import pdqueue


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))


if _TEST_DIR.startswith("/vagrant/"):
    print "************ WARNING!!!! ************"
    print "test_pdqueue can't run queue tests on vagrant shared mount:", _TEST_DIR
    _TEST_DIR = "/tmp/test_pdqueue_alternate"
    print "Using alternate directory:", _TEST_DIR


TEST_QUEUE_DIR = os.path.join(_TEST_DIR, "test_queue")
TEST_DB_DIR = os.path.join(_TEST_DIR, "test_db")
BACKOFF_INTERVAL = 5
ERROR_RETRY_LIMIT = 3


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
        for t in pdqueue.QUEUE_SUBDIRS:
            os.makedirs(os.path.join(TEST_QUEUE_DIR, t))
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
            default_umask=022
            )
        q = PDQueue(
            queue_dir=TEST_QUEUE_DIR,
            lock_class=NoOpLock,
            time_calc=mock_time,
            event_size_max_bytes=10,
            backoff_interval=BACKOFF_INTERVAL,
            retry_limit_for_possible_errors=ERROR_RETRY_LIMIT,
            backoff_db=MockDB(),
            counter_db=MockDB()
            )
        return eq, q

    def test__open_creat_excl(self):
        from pdagent.pdqueue import _open_creat_excl
        eq, _ = self.new_queue()
        fname_abs = eq._abspath("", "_open_creat_excl.txt")
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

    def test__link(self):
        from pdagent.pdqueue import _link
        eq, _ = self.new_queue()
        f1 = eq._abspath("", "_link1.txt")
        f2 = eq._abspath("", "_link2.txt")
        self.assertFalse(os.path.exists(f1))
        self.assertFalse(os.path.exists(f2))

        open(f1, "w").write("foo")
        self.assertEquals(open(f1).read(), "foo")

        self.assertTrue(_link(f1, f2))
        self.assertEquals(open(f1).read(), "foo")
        self.assertEquals(open(f2).read(), "foo")

        self.assertFalse(_link(f1, f2))

        open(f1, "w").write("bar")
        self.assertFalse(_link(f1, f2))
        self.assertEquals(open(f1).read(), "bar")
        self.assertEquals(open(f2).read(), "bar")

        os.unlink(f1)
        self.assertFalse(os.path.exists(f1))
        self.assertEquals(open(f2).read(), "bar")

        os.unlink(f2)
        self.assertFalse(os.path.exists(f1))
        self.assertFalse(os.path.exists(f2))


    def test_enqueue_and_dequeue(self):
        eq, q = self.new_queue()

        self.assertEquals(q._queued_files(), [])

        f_foo, _ = eq.enqueue("svckey1", "foo")
        self.assertEquals(q._queued_files(), [f_foo])
        self.assertEquals(open(q._abspath("pdq", f_foo)).read(), "foo")

        q.time.sleep(0.05)
        f_bar, _ = eq.enqueue("svckey2", "bar")  # different service key
        self.assertEquals(q._queued_files(), [f_foo, f_bar])
        self.assertEquals(open(q._abspath("pdq", f_foo)).read(), "foo")
        self.assertEquals(open(q._abspath("pdq", f_bar)).read(), "bar")

        q.time.sleep(0.05)
        f_baz, _ = eq.enqueue("svckey1", "baz")
        self.assertEquals(q._queued_files(), [f_foo, f_bar, f_baz])
        self.assertEquals(open(q._abspath("pdq", f_foo)).read(), "foo")
        self.assertEquals(open(q._abspath("pdq", f_bar)).read(), "bar")
        self.assertEquals(open(q._abspath("pdq", f_baz)).read(), "baz")

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
            fd = open(q._abspath("suc", f))
            success_contents.append(fd.read())
            fd.close()
        self.assertEquals(success_contents, ["foo", "bar", "baz"])

    def test_bad_fnames(self):
        eq, q = self.new_queue()

        def make_bad_entry(n):
            badf = q._abspath("pdq", n)
            open(badf, "w").close()

        make_bad_entry("0_extra_underscore_random.txt")
        make_bad_entry("0_no_extension")
        f_foo, _ = eq.enqueue("svckey", "foo")
        make_bad_entry("notinttime_servicekey.txt")
        make_bad_entry("notenoughunderscores.txt")

        q.flush(
            lambda s, i: ConsumeEvent.CONSUMED,
            lambda: False
            )

        self.assertEquals(len(q._queued_files("pdq")), 0)
        self.assertEquals(
            q._queued_files("suc"),
            [
                "0_extra_underscore_random.txt",
                f_foo,
                ]
            )
        self.assertEquals(
            q._queued_files("err"),
            [
                "0_no_extension",
                "notenoughunderscores.txt",
                "notinttime_servicekey.txt",
                ]
            )

    def test_consume_error(self):
        # The item should get tagged as error, and not be available for
        # further consumption, if consumption causes error.
        eq, q = self.new_queue()
        f_foo, _ = eq.enqueue("svckey", "foo")

        def erroneous_consume_foo(s, i):
            self.assertEquals("foo", s)
            self.assertEquals(f_foo, i)
            return ConsumeEvent.BAD_ENTRY
        q.dequeue(erroneous_consume_foo)

        self.assertEquals(len(q._queued_files("err")), 1)
        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s: ConsumeEvent.CONSUMED
            )

    def test_dequeue_no_lock_on_no_work(self):
        eq, q = self.new_queue()

        trace = []
        f_delete_me = []

        class FileDeletingLockClass:
            def __init__(self, lockfile):
                trace.append("Li")

            def acquire(self):
                if f_delete_me:
                    f = f_delete_me.pop()
                    trace.append("D")
                    trace.append(f)
                    os.remove(f)
                trace.append("La")

            def release(self):
                trace.append("Lr")
        q.lock_class = FileDeletingLockClass

        # If there are no pending items, dequeue should return without
        # acquiring the lock.
        self.assertRaises(EmptyQueueError, q.dequeue, None)
        self.assertEquals(trace, [])

        f_foo, _ = eq.enqueue("svckey", "foo")

        # If there is a pending item, dequeue should recheck the queue
        # after acquiring the lock.
        f_foo_abs = q._abspath("pdq", f_foo)
        f_delete_me.append(f_foo_abs)
        self.assertRaises(EmptyQueueError, q.dequeue, None)
        self.assertEquals(trace, ["Li", "D", f_foo_abs, "La", "Lr"])

    def test_huge_event_not_processed(self):
        # The item should get tagged as error, and not be available for
        # further consumption.
        eq, q = self.new_queue()
        f, _ = eq.enqueue("svckey", "huuuuuuuuge")
        self.assertEquals(q._queued_files(), [f])

        def unexpected_consume(s, i):
            self.fail("Unexpected event %s" % s)
        q.dequeue(unexpected_consume)  # consume function must not be called.

        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(len(q._queued_files("err")), 1)
        self._assertCounterData(q, (0, 1))

    def test_backoff_bad_event(self):
        # The item and all other items for same service key must get backed off
        # until backoff limit is hit, then the offending item should get tagged
        # as error, and not be available for further consumption.
        eq, q = self.new_queue()
        e1_1, _ = eq.enqueue("svckey1", "foo")
        q.time.sleep(0.05)
        e1_2, _ = eq.enqueue("svckey1", "bar")
        q.time.sleep(0.05)
        e2_1, _ = eq.enqueue("svckey2", "baz")

        events_processed = []
        count = 0
        # total attempts including backoffs, after which corrective action
        # for bad event kicks in, i.e. kicks in for the max-th attempt.
        max_total_attempts = ERROR_RETRY_LIMIT + 1

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
        self.assertEquals(len(q._queued_files("err")), 0)  # no error yet.
        self._assertBackoffData(q, [("svckey1", 1, 0)])
        self._assertCounterData(q, (1, 0))

        # retry immediately. later-retriable events must not be processed.
        events_processed = []
        q.flush(consume_with_backoff, lambda: False)
        self.assertEquals(len(events_processed), 0)
        self.assertEquals(q._queued_files(), [e1_1, e1_2])
        self.assertEquals(len(q._queued_files("err")), 0)
        self._assertBackoffData(q, [("svckey1", 1, 0)])
        self._assertCounterData(q, (1, 0))

        # retry just shy of max allowed times.
        for i in range(2, max_total_attempts):
            q.time.sleep(BACKOFF_INTERVAL)
            count += 1
            events_processed = []
            q.flush(consume_with_backoff, lambda: False)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(q._queued_files(), [e1_1, e1_2])  # bad svckey's
            self.assertEquals(len(q._queued_files("err")), 0)  # no error yet
            self._assertBackoffData(q, [("svckey1", i, i-1)])
            self._assertCounterData(q, (1, 0))

        # retry now. there should be no more backoffs, bad event should be
        # kicked out, and next event should finally be processed.
        q.time.sleep(BACKOFF_INTERVAL)
        count += 1
        events_processed = []
        q.flush(consume_with_backoff, lambda: False)
        self.assertEquals(events_processed, ["foo", "bar"])  # bad + next events
        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(
            q._queued_files("err"),
            [e1_1]
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
        e1_1, _ = eq.enqueue("svckey1", "foo")
        q.time.sleep(0.05)
        e1_2, _ = eq.enqueue("svckey1", "bar")
        q.time.sleep(0.05)
        e2_1, _ = eq.enqueue("svckey2", "baz")

        events_processed = []
        count = 0
        # total attempts including backoffs, after which corrective action
        # for bad event kicks in, i.e. kicks in for the max-th attempt.
        max_total_attempts = ERROR_RETRY_LIMIT + 1

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
        self.assertEquals(len(q._queued_files("err")), 0)  # no error yet.
        self._assertBackoffData(q, [("svckey1", 1, 0)])
        self._assertCounterData(q, (1, 0))

        # retry immediately. later-retriable events must not be processed.
        events_processed = []
        q.flush(consume_with_backoff, lambda: False)
        self.assertEquals(len(events_processed), 0)
        self.assertEquals(q._queued_files(), [e1_1, e1_2])
        self.assertEquals(len(q._queued_files("err")), 0)
        self._assertBackoffData(q, [("svckey1", 1, 0)])
        self._assertCounterData(q, (1, 0))

        # retry just shy of max allowed times.
        for i in range(2, max_total_attempts):
            q.time.sleep(BACKOFF_INTERVAL)
            count += 1
            events_processed = []
            q.flush(consume_with_backoff, lambda: False)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(q._queued_files(), [e1_1, e1_2])  # bad svckey's
            self.assertEquals(len(q._queued_files("err")), 0)  # no error yet
            self._assertBackoffData(q, [("svckey1", i, i-1)])
            self._assertCounterData(q, (1, 0))

        # try a couple more times (we exceed max attempts going forward) --
        # bad event is still processed.
        for i in [0, 1]:
            q.time.sleep(BACKOFF_INTERVAL)
            count += 1
            events_processed = []
            q.flush(consume_with_backoff, lambda: False)
            self.assertEquals(events_processed, ["foo"])  # bad event
            self.assertEquals(q._queued_files(), [e1_1, e1_2])  # bad svckey's
            self.assertEquals(len(q._queued_files("err")), 0)  # still no errors
            self._assertBackoffData(
                q,
                [("svckey1", max_total_attempts + i, -1)]
                )
            self._assertCounterData(q, (1, 0))

        # retry now (much after max_backoff_attempts), with no bad event.
        q.time.sleep(BACKOFF_INTERVAL)
        count += 1
        events_processed = []
        q.flush(consume_with_backoff, lambda: False)
        self.assertEquals(events_processed, ["foo", "bar"])  # all good events
        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(len(q._queued_files("err")), 0)   # no errors
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
        f_foo, _ = eq.enqueue("svckey1", "foo")
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
        self.assertEquals(len(q._queued_files("err")), 0)  # no error events
        self._assertCounterData(q, (0, 0))

        # retry. all events must now be processed.
        count += 1
        events_processed = []
        q.flush(consume_with_stopall, lambda: False)
        self.assertEquals(events_processed, ["foo", "bar", "baz"])
        self.assertEquals(len(q._queued_files()), 0)
        self.assertEquals(len(q._queued_files("err")), 0)  # no error events
        self._assertCounterData(q, (3, 0))

        # and now, the queue must be empty.
        self.assertRaises(
            EmptyQueueError, q.dequeue, lambda s: ConsumeEvent.CONSUMED
            )

    def test_enqueue_never_blocks(self):
        # test that a read lock during dequeue does not block an enqueue
        eq, q = self.new_queue()
        f_foo, _ = eq.enqueue("svckey", "foo")

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

        f_bar, _ = eq.enqueue("svckey", "bar")

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

    def test_restrictive_umask(self):
        orig_umask = os.umask(0777)
        try:
            eq, q = self.new_queue()
            f_foo, problems = eq.enqueue("svckey", "foo")

            # umask was flagged as a problem...
            self.assertEquals(problems, [EnqueueWarnings.UMASK_TOO_RESTRICTIVE])
            # ... but event was enqueued with the correct permissions.
            self.assertEquals(q._queued_files(), [f_foo])
            f_stmode = os.stat(q._abspath("pdq", f_foo)).st_mode
            fmode = f_stmode & (stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            self.assertEquals(fmode, eq.enqueue_file_mode)
        finally:
            os.umask(orig_umask)

    def test_resurrect(self):
        eq, q = self.new_queue()
        fnames = []
        fnames.append(eq.enqueue("svckey1", "foo")[0])
        fnames.append(eq.enqueue("svckey1", "bar")[0])
        fnames.append(eq.enqueue("svckey2", "baz")[0])
        fnames.append(eq.enqueue("svckey2", "boo")[0])
        fnames.append(eq.enqueue("svckey3", "bam")[0])
        for i in [0, 2, 4]:
            q._unsafe_change_event_type(fnames[i], "pdq", "err")

        self.assertEquals(len(q._queued_files()), 2)
        self.assertEquals(len(q._queued_files("err")), 3)

        q.resurrect("svckey1")
        self.assertEquals(len(q._queued_files()), 3)
        errfiles = q._queued_files("err")
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
        self.assertEquals(len(q._queued_files("err")), 0)

        # counters should not be touched.
        self._assertCounterData(q, None)

    def test_stats(self):
        eq, q = self.new_queue()
        events = ["e11", "e12", "e13", "e21", "e22", "e31", "e32", "e41", "e42"]
        fnames = []
        for e in events:
            # events are in the form e<svckey#><event#>
            k = e[1]
            fnames.append(eq.enqueue("svckey%s" % k, e)[0])
            eq.time.sleep(5)

        # 1 error for svckey1; 2 for svckey2
        for i in [0, 3, 4]:
            q._unsafe_change_event_type(fnames[i], "pdq", "err")
        # 1 success for svckey1; 2 for svckey4
        for i in [2, 7, 8]:
            q._unsafe_change_event_type(fnames[i], "pdq", "suc")
        # that leaves 1 pending for svckey1; 2 for svckey3

        # also, let's throttle svckey2...
        q.backoff_info.increment("svckey2")
        # ... and increment some counters.
        for _ in range(20):
            q.counter_info.increment_success()
        for _ in range(2):
            q.counter_info.increment_failure()

        def stats_by_state(data):
            stats = dict()
            for d in data:
                (service_type, count, oldest_age, newest_age,
                    service_key_count) = d
                if count:
                    stats[service_type + "_events"] = {
                        "count": count,
                        "oldest_age_secs": oldest_age,
                        "newest_age_secs": newest_age,
                        "service_keys_count": service_key_count
                        }
            return stats

        snapshot_stats = stats_by_state([
            ("pending", 3, 40, 15, 2),
            ("succeeded", 3, 35, 5, 2),
            ("failed", 3, 45, 25, 2),
            ])
        snapshot_stats["throttled_service_keys_count"] = 1
        expected_stats = {
            "snapshot": snapshot_stats,
            "aggregate": {
                "successful_events_count": 20,
                "failed_events_count": 2,
                "started_on": "some_utc_time"
                }
            }
        self.assertEqual(q.get_stats(detailed_snapshot=True), expected_stats)

        snapshot_stats.pop("succeeded_events")
        snapshot_stats.pop("failed_events")
        self.assertEqual(q.get_stats(), expected_stats)

        # test per-service-key stats.
        snapshot_stats.pop("pending_events")
        snapshot_stats["svckey1"] = stats_by_state([
            ("pending", 1, 40, 40, 1),
            ("succeeded", 1, 35, 35, 1),
            ("failed", 1, 45, 45, 1),
            ])
        snapshot_stats["svckey2"] = stats_by_state([
            ("pending", 0, 0, 0, 0),
            ("succeeded", 0, 0, 0, 0),
            ("failed", 2, 30, 25, 1),
            ])
        snapshot_stats["svckey3"] = stats_by_state([
            ("pending", 2, 20, 15, 1),
            ("succeeded", 0, 0, 0, 0),
            ("failed", 0, 0, 0, 0),
            ])
        snapshot_stats["svckey4"] = stats_by_state([
            ("pending", 0, 0, 0, 0),
            ("succeeded", 2, 10, 5, 1),
            ("failed", 0, 0, 0, 0),
            ])
        self.assertEqual(
            q.get_stats(detailed_snapshot=True, per_service_key_snapshot=True),
            expected_stats
            )

        # test service-key stats for a given service key.
        snapshot_stats.pop("svckey2")
        snapshot_stats.pop("svckey3")
        snapshot_stats.pop("svckey4")
        self.assertEqual(
            q.get_stats(
                detailed_snapshot=True,
                per_service_key_snapshot=True,
                service_key="svckey1"
                ),
            expected_stats
            )

    def test_cleanup(self):
        # simulate enqueues done a while ago.
        eq, q = self.new_queue()

        def enqueue_before(sec, prefix="pdq"):
            enqueue_time_us = (int(time.time()) - sec) * (1000 * 1000)
            fname = "%d_%s.txt" % (
                enqueue_time_us,
                "svckey%d" % (enqueue_time_us % 10)
                )
            fpath = os.path.join(q.queue_dir, prefix, fname)
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
        invalid = "invalid.txt"
        os.close(os.open(os.path.join(q.queue_dir, "tmp", invalid), os.O_CREAT))

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
                retries[svc_key] = int(q.time.time() + BACKOFF_INTERVAL)

        self.assertEqual(backup_data, {
            "attempts": attempts,
            "next_retries": retries
            })


    def _assertCounterData(self, q, data):
        counter_db = q.counter_info._db
        counter_data = counter_db.get()

        try:
            counter_db.cached_started_on
        except AttributeError:
            # "started_on" must be generated if not present already.
            self.assertNotEquals(counter_data["started_on"], None)
            counter_db.cached_started_on = counter_data["started_on"]
        # "started_on" must not change once generated.
        expected = {
            "started_on": counter_db.cached_started_on
            }

        if data:
            success, failure = data
            if success != 0:
                expected["successful_events_count"] = success
            if failure != 0:
                expected["failed_events_count"] = failure

        self.assertEqual(counter_data, expected)



if __name__ == '__main__':
    unittest.main()
