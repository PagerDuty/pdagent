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

import inspect
import os
import time
import unittest

from pdagent.thirdparty.filelock import FileLock, LockTimeoutException


_TEST_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_HELPER_PY = os.path.join(_TEST_DIR, "filelock-test-helper.py")

TEST_LOCK_FILE = os.path.join(_TEST_DIR, "test_filelock_lock.txt")


def run_helper(test_name=None):
    if not test_name:
        # default to the same name as the calling test method
        test_name = inspect.stack()[1][3]
    e = os.system("python %s %s" % (TEST_HELPER_PY, test_name))
    exit_code, signal = e / 256, e % 256
    return exit_code, signal


class FileLockTest(unittest.TestCase):

    def setUp(self):
        if os.path.exists(TEST_LOCK_FILE):
            os.unlink(TEST_LOCK_FILE)

        self.lock = FileLock(TEST_LOCK_FILE)
        # Ensure that some other process is not holding the lock
        self.lock.acquire()
        self.lock.release()
        self.thread = None

    def tearDown(self):
        if self.thread:
            self.thread.join()
            self.thread = None

    def runInThread(self, f):
        from threading import Thread
        self.thread = Thread(target=f)
        self.thread.start()

    def test_spawn_ok(self):
        # this test just to check if we're spawning the helper correctly
        e = run_helper()
        self.assertEqual(e, (10, 0))

    def test_simple_lock_internal(self):
        self.assertFalse(os.path.exists(TEST_LOCK_FILE))
        self.lock.acquire()
        self.assertTrue(os.path.exists(TEST_LOCK_FILE))
        self.lock.release()
        self.assertFalse(os.path.exists(TEST_LOCK_FILE))

    def test_simple_lock(self):
        self.assertEqual(run_helper(), (20, 0))
        self.assertFalse(os.path.exists(TEST_LOCK_FILE))

    def test_simple_lock_file_exists(self):
        open(TEST_LOCK_FILE, "w").write("-1\n")
        self.assertEqual(run_helper("test_simple_lock"), (20, 0))
        self.assertFalse(os.path.exists(TEST_LOCK_FILE))

    def test_lock_wait(self):
        trace = []

        def f():
            try:
                trace.append("A")
                time.sleep(1)  # Pause to allow helper acquire the lock
                trace.append("B")
                self.lock.acquire()
                trace.append("C")
                time.sleep(2)
                trace.append("D")
                self.lock.release()
                trace.append("E")
            except LockTimeoutException:
                trace.append("T")
            except:
                trace.append("X")

        self.runInThread(f)
        time.sleep(0.1)  # Allow thread to run
        self.assertEqual(trace, ["A"])

        self.assertEqual(run_helper(), (25, 0))

        self.assertEqual(trace, ["A", "B"])

        time.sleep(2.1)  # Allow thread to finish
        self.assertEqual(trace, ["A", "B", "C", "D", "E"])

    def test_lock_timeout(self):
        self.lock.acquire()
        self.assertEqual(run_helper(), (30, 0))
        self.lock.release()

    def test_lock_timeout_other_way_around(self):
        trace = []
        self.lock.timeout = 1

        def f():
            try:
                trace.append("A")
                time.sleep(1)  # Pause to allow helper acquire the lock
                trace.append("B")
                self.lock.acquire()
                trace.append("C")
                self.lock.release()
                trace.append("D")
            except LockTimeoutException:
                trace.append("T")
            except:
                trace.append("X")

        self.runInThread(f)
        time.sleep(0.1)  # Allow thread to run
        self.assertEqual(trace, ["A"])

        self.assertEqual(run_helper(), (35, 0))

        self.assertEqual(trace, ["A", "B", "T"])

    def test_exit_without_release(self):
        # python graceful exit should call __del__ & result in
        # release & delete of lock file
        self.assertEqual(run_helper(), (40, 0))
        self.assertFalse(os.path.exists(TEST_LOCK_FILE))
        self.lock.acquire()
        self.lock.release()

    def test_kill_releases_lock(self):
        # python being force killed will release the lock but leave the file
        self.assertTrue(
            run_helper() in [
                (0, 9),  # mac, centos
                (128 + 9, 0),  # ubuntu
                ]
            )
        self.assertTrue(os.path.exists(TEST_LOCK_FILE))
        self.lock.acquire()
        self.lock.release()
        self.assertFalse(os.path.exists(TEST_LOCK_FILE))


if __name__ == '__main__':
    unittest.main()
