
import inspect
import os
import shutil
import time
import unittest

from pdagent.filelock import FileLock, FileLockException


TEST_HELPER_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_filelock-helper.py")

TEST_LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_filelock_lock.txt")


def run_helper():
    test_name = inspect.stack()[1][3]  # call the helper test with same name as the calling test
    e = os.system("python %s %s" % (TEST_HELPER_PY, test_name))
    e = e / 256  # needed on unix to get actual exit code
    return e


class FileLockTest(unittest.TestCase):

    def setUp(self):
        if os.path.exists(TEST_LOCK_FILE):
            os.unlink(TEST_LOCK_FILE)

    def test_spawn_ok(self):
        # this test just to check if we're spawning the helper correctly
        e = run_helper()
        self.assertEqual(e, 10)

    def test_simple_lock(self):
        self.assertEqual(run_helper(), 20)

    def test_lock_timeout(self):
        l = FileLock(TEST_LOCK_FILE)
        l.acquire()
        e = run_helper()
        self.assertEqual(e, 30)
        l.release()


if __name__ == '__main__':
    unittest.main()
