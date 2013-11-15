import fcntl
import os
import re
import time

class EmptyQueue(Exception):
    pass


class PDQueue(object):
    """
    A directory based queue for PagerDuty events.

    Notes:
    - Designed for multiple processes concurrently using the queue.
    - Each entry in the queue is written to a separate file in the queue directory.
    - Entry file names are generated so that sorting by name results in queue order.
    - Concurrent dequeues are serialized with an exclusive dequeue lock.
    - Readers (dequeue) will not block writers (enqueue).
    - TBD: Concurrent enqueues are serialized with an exclusive enqueue lock.
    - TBD: Is enqueue atomic in the face of error?
    """

    def __init__(self, queue_dir, lock_class):
        self.queue_dir = queue_dir
        self.lock_class = lock_class
        #
        self._create_queue_dir()
        self._verify_permissions()
        #
        self._dequeue_lockfile = os.path.join(self.queue_dir, "dequeue_lock.txt")

    def _create_queue_dir(self):
        if not os.access(self.queue_dir, os.F_OK):
            os.mkdir(self.queue_dir, 0700)

    def _verify_permissions(self):
        if not (os.access(self.queue_dir, os.R_OK)
            and os.access(self.queue_dir, os.W_OK)):
            raise Exception("Can't read/write to directory %s, please check permissions." % self.queue_dir)

    # Get the list of queued files from the queue directory
    def _queued_files(self):
        fnames = [f for f in os.listdir(self.queue_dir) if f.startswith("pd_")]
        fnames.sort()
        return fnames

    def _abspath(self, fname):
        return os.path.join(self.queue_dir, fname)

    def enqueue(self, s):
        process_id = os.getpid()
        time_seconds = int(time.time())
        fname = "pd_%d_%d" % (time_seconds, process_id)
        fname_abs = self._abspath(fname)
        if os.path.exists(fname_abs):
            raise AssertionError, "Queue entry file already exists: %s" % fname_abs
        with open(fname_abs, "w", 0600) as f:
            f.write(s)
        return fname

    def dequeue(self, consume_func):
        #
        lock = self.lock_class(self._dequeue_lockfile)
        lock.acquire()
        try:
            #
            file_names = self._queued_files()
            if not len(file_names):
                raise EmptyQueue
            fname = file_names[0]
            fname_abs = self._abspath(fname)
            # TODO: handle missing file or other errors
            f = open(fname_abs)
            try:
                s = f.read()
            finally:
                f.close()
            #
            consumed = consume_func(s)
            #
            if consumed:
                # TODO: handle/log delete error!
                os.remove(fname_abs)
        finally:
            lock.release()

