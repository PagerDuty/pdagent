
import os
import shutil
from threading import Lock, Thread
import time
import unittest

from pdagent.pdqueue import PDQueue, EmptyQueue


TEST_QUEUE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_queue")


def _f_lock_noop(lf):
    def f_release():
        pass
    return f_release


class PDQueueTest(unittest.TestCase):

    def setUp(self):
        if os.path.exists(TEST_QUEUE_DIR):
            shutil.rmtree(TEST_QUEUE_DIR)

    def newQueue(self, f_lock=_f_lock_noop):
        return PDQueue(TEST_QUEUE_DIR, f_lock)

    def test_init_creates_directory(self):
        self.assertFalse(os.path.exists(TEST_QUEUE_DIR))
        self.newQueue()
        self.assertTrue(os.path.exists(TEST_QUEUE_DIR))

    def test_enqueue_and_dequeue(self):
        q = self.newQueue()
        #
        self.assertEquals(q._queued_files(), [])
        #
        f_foo = q.enqueue("foo")
        self.assertEquals(q._queued_files(), [f_foo])
        self.assertEquals(q._readfile(f_foo), "foo")
        #
        # FIXME: need sleep to avoid name clash in same second
        import time; time.sleep(1)
        #
        f_bar = q.enqueue("bar")
        self.assertEquals(q._queued_files(), [f_foo, f_bar])
        self.assertEquals(q._readfile(f_foo), "foo")
        self.assertEquals(q._readfile(f_bar), "bar")
        #
        def consume_foo(s): self.assertEquals("foo", s); return True
        q.dequeue(consume_foo)
        #
        def consume_bar(s): self.assertEquals("bar", s); return True
        q.dequeue(consume_bar)
        #
        # check queue is empty
        self.assertEquals(q._queued_files(), [])
        self.assertRaises(EmptyQueue, q.dequeue, lambda s: True)


    def test_dont_consume(self):
        # The item should stay in the queue if we don't consume it.
        q = self.newQueue()
        q.enqueue("foo")
        #
        def dont_consume_foo(s): self.assertEquals("foo", s); return False
        q.dequeue(dont_consume_foo)
        q.dequeue(dont_consume_foo)
        #
        def consume_foo(s): self.assertEquals("foo", s); return True
        q.dequeue(consume_foo)
        #
        self.assertRaises(EmptyQueue, q.dequeue, lambda s: True)


    def test_enqueue_never_blocks(self):
        # test that a read lock during dequeue does not block an enqueue
        pass

    def test_parallel_dequeque(self):
        # test that a dequeue blocks another dequeue using locking
        #
        def make_f_lock(name):
            def f_lock(lf):
                self.assertEquals(dequeue_lockfile, lf)
                trace.append(name + "_A1")
                lock.acquire()
                trace.append(name + "_A2")
                def f_release():
                    trace.append(name + "_R")
                    lock.release()
                return f_release
            return f_lock
        # setup queue with one item
        q1 = self.newQueue(make_f_lock("q1"))
        q2 = self.newQueue(make_f_lock("q2"))
        q1.enqueue("foo")
        #
        dequeue_lockfile = q1._dequeue_lockfile
        trace = []
        lock = Lock()
        #
        def dequeue2():
            try:
                def consume2(s):
                    self.fail() # consume2 shouldn't be called!
                q2.dequeue(consume2)
            except EmptyQueue:
                trace.append("q2_EQ")
        #
        thread_dequeue2 = Thread(target=dequeue2)
        #
        def consume1(s):
            # check that q1 acquired the lock
            self.assertEquals(trace, ["q1_A1", "q1_A2"])
            # start dequeue2 in separate thread to recreate concurrent queue access
            thread_dequeue2.start()
            # give thread time to run - it should be stuck in lock acquire
            time.sleep(0.1)
            self.assertEquals(trace, ["q1_A1", "q1_A2", "q2_A1"])
            # consume the item
            trace.append("q1_C:" + s)
            return True
        #
        q1.dequeue(consume1)
        # give thread time to acquire the just released lock & run to completion
        time.sleep(0.1)
        #
        self.assertEquals(trace, [
            "q1_A1", "q1_A2", "q2_A1",
            "q1_C:foo", "q1_R",
            "q2_A2", "q2_R",
            "q2_EQ",
             ])



if __name__ == '__main__':
    unittest.main()
