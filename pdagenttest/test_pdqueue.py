
import os
import shutil
import unittest

from pdagent.pdqueue import PDQueue


TEST_QUEUE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_queue")


class PDQueueTest(unittest.TestCase):

    def setUp(self):
        # delete leftover from previous test run
        if os.path.exists(TEST_QUEUE_DIR):
            shutil.rmtree(TEST_QUEUE_DIR)

    def makeQueue(self):
        return PDQueue(TEST_QUEUE_DIR)

    def test_init_creates_directory(self):
        self.assertFalse(os.path.exists(TEST_QUEUE_DIR))
        q = PDQueue(TEST_QUEUE_DIR)
        self.assertTrue(os.path.exists(TEST_QUEUE_DIR))

    def test_enqueue_and_dequeue(self):
        q = PDQueue(TEST_QUEUE_DIR)
        # TODO:
        # - enqueue 1 string
        # - inspect file - perhaps enqueue returns filename?
        # - enqueue 1 string
        #     we may want to sleep a short while to avoid queue timestamp clash
        # - inspect directory - should have 2 files on specific names
        # - dequeue 1 string - check file gone
        # - dequeue 1 string
        # - inspect directory - should be empty

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
