
import os
import signal
import sys
import time

from pdagent.filelock import FileLock, FileLockException
from pdagenttest.test_filelock import TEST_LOCK_FILE

lock = FileLock(TEST_LOCK_FILE, timeout=1)


def test_spawn_ok():
    return 10

def test_simple_lock():
    lock.acquire()
    time.sleep(1)
    lock.release()
    return 20

def test_lock_timeout():
    try:
        lock.acquire()
    except FileLockException:
        return 30
    return 31

def test_exit_without_release():
    lock.acquire()
    return 40

def test_kill_releases_lock():
    lock.acquire()
    os.kill(os.getpid(), signal.SIGKILL)
    return 50


if __name__ == "__main__":
    args = sys.argv
    if len(args) != 2: sys.exit(2)  # wrong number of args
    #
    _test_func_name = args[1]
    if not _test_func_name.startswith("test_"): sys.exit(5)  # bad test name
    #
    main_module = sys.modules["__main__"]
    _test_func = getattr(main_module, _test_func_name, None)
    if not _test_func: sys.exit(6)  # no such test
    #
    exit_code = _test_func()
    if exit_code is None: sys.exit(7)  # missing exit code
    if exit_code != 0 and exit_code < 10: sys.exit(8)  # reserved exit code
    sys.exit(exit_code)


