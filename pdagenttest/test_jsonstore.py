import errno
import json
import os
import stat
import unittest

from pdagent.jsonstore import JsonStore


_TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_db")
_TEST_STORE_NAME = "test"
_TEST_STORE_FILE = os.path.join(_TEST_DIR, _TEST_STORE_NAME)

class JsonStoreTest(unittest.TestCase):

    def setUp(self):
        try:
            os.makedirs(_TEST_DIR)
        except OSError as e:
            if e.errno is not errno.EEXIST:
                raise
        try:
            os.unlink(_TEST_STORE_FILE)
        except OSError as e:
            if e.errno is not errno.ENOENT:
                raise
        self.store = JsonStore(_TEST_STORE_NAME, _TEST_DIR)

    def test_first_read(self):
        j = self.store.get()
        self.assertIsNone(j)

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
