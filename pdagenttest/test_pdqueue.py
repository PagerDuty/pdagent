
import unittest
import os


TEST_QUEUE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_queue")


class PDQueueTest(unittest.TestCase):

    def setUp(self):
        # delete test queue directory
        # create queue
        pass

    def test_dummy(self):
        a = 1 + 1
        self.assertEquals(2, a)

    def test_x(self):
        pass


    if __name__ == '__main__':
        unittest.main()
