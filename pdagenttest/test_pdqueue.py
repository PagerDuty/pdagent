
import os
import shutil
import unittest

from pdagent.pdqueue import PDQueue, EmptyQueue


TEST_QUEUE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_queue")


class PDQueueTest(unittest.TestCase):

    def setUp(self):
        if os.path.exists(TEST_QUEUE_DIR):
            shutil.rmtree(TEST_QUEUE_DIR)

    def newQueue(self):
        return PDQueue(TEST_QUEUE_DIR)

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


    def test_could_not_consume(self):
        # The item should stay in the queue if we can't consume it.
        pass

    def test_enqueue_never_blocks(self):
        # test that a read lock during dequeue does not block an enqueue
        pass

    def test_parallel_reading(self):
        # test that a read blocks another read using locking
        pass



if __name__ == '__main__':
    unittest.main()
