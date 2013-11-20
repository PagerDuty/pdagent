import errno
import os
import time


class EmptyQueue(Exception):
    pass


class PDQueue(object):
    """
    A directory based queue for PagerDuty events.

    Notes:
    - Designed for multiple processes concurrently using the queue.
    - Each entry in the queue is written to a separate file in the queue directory.
    - Files are named so that sorting by file name is queue order.
    - Concurrent enqueues use exclusive file create & retries to avoid using the same file name.
    - Concurrent dequeues are serialized with an exclusive dequeue lock.
    - A dequeue will hold the exclusive lock until the consume callback is done.
    - dequeue never block enqueue, and enqueue never blocks dequeue.
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
        fnames = [f for f in os.listdir(self.queue_dir) if f.startswith("pdq_")]
        fnames.sort()
        return fnames

    def _abspath(self, fname):
        return os.path.join(self.queue_dir, fname)

    def enqueue(self, s):
        # write to an exclusive temp file
        _, tmp_fname_abs, tmp_fd = self._open_creat_excl_with_retry("tmp_%d.txt")
        os.write(tmp_fd, s)
        # get an exclusive queue entry file
        pdq_fname, pdq_fname_abs, pdq_fd = self._open_creat_excl_with_retry("pdq_%d.txt")
        # since we're exclusive on both files, we can safely rename the tmp file
        os.close(tmp_fd)
        os.rename(tmp_fname_abs, pdq_fname_abs)
        os.close(pdq_fd)
        #
        return pdq_fname

    def _open_creat_excl_with_retry(self, fname_fmt):
        n = 0
        while True:
            t_millisecs = int(time.time() * 1000)
            fname = fname_fmt % t_millisecs
            fname_abs = self._abspath(fname)
            #
            try:
                fd = os.open(fname_abs, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            except OSError, e:
                if e.errno == errno.EEXIST:
                    n += 1
                    if n < 100:
                        time.sleep(0.001)
                        continue
                    else:
                        raise Exception, \
                            "Too many retries! (Last attempted name: %s)" % fname_abs
                else:
                    raise
            else:
                return fname, fname_abs, fd

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

    # TODO: / FIXME: need to clean up old abandonded tmp_*.txt

