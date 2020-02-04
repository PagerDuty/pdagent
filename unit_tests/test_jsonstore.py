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

import errno
import json
import os
import stat
import unittest

from pdagent.jsonstore import JsonStore


# not using a path under agent code directory because it is the sync'ed
# directory in the VMs, and we need to change permissions of directories in our
# tests, and permissions of sync'ed directories cannot be changed in VMs.
_TEST_DIR = os.path.join("/tmp", "test_db")
_TEST_STORE_NAME = "test"
_TEST_STORE_FILE = os.path.join(_TEST_DIR, _TEST_STORE_NAME)


class JsonStoreTest(unittest.TestCase):

    def setUp(self):
        try:
            os.makedirs(_TEST_DIR)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        try:
            os.unlink(_TEST_STORE_FILE)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        self.store = JsonStore(_TEST_STORE_NAME, _TEST_DIR)

    def test_first_read(self):
        j = self.store.get()
        self.assertTrue(j is None)

    def test_write_and_read(self):
        j = {
            "foo": "bar",
            "baz": 1
            }
        self.store.set(j)
        self.assertEqual(self.store.get(), j)
        # ensure that json is persisted.
        self.assertTrue(os.path.isfile(_TEST_STORE_FILE))
        fp = None
        try:
            fp = open(_TEST_STORE_FILE, "r")
            self.assertEqual(json.load(fp), j)
        finally:
            if fp:
                fp.close()
        # ensure that a different store can pick up persisted content.
        self.assertEqual(JsonStore(_TEST_STORE_NAME, _TEST_DIR).get(), j)

    def test_failed_write(self):
        j = {
            "foo": "bar",
            "baz": True
            }
        self.store.set(j)   # successful write.
        # now make file not writable, and check that set fails.
        try:
            os.chmod(_TEST_DIR, stat.S_IREAD | stat.S_IEXEC)
            k = dict(j)
            k["baz"] = False
            self.assertRaises(IOError, self.store.set, k)
            # old value is retained in this case.
            self.assertEqual(self.store.get(), j)
        finally:
            os.chmod(
                _TEST_DIR,
                stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

    def test_bad_data(self):
        j = {
            "foo": "bar",
            "baz": True
            }
        self.store.set(j)   # successful write.
        # now corrupt the persisted data.
        out = open(_TEST_STORE_FILE, "w")
        out.write("bad json!")
        out.close()
        # bad json => data is cleared.
        self.assertEqual(self.store.get(), None)

if __name__ == '__main__':
    unittest.main()
