import errno
import os
import time
from constants import EVENT_CONSUMED, EVENT_CONSUME_ERROR


class EmptyQueue(Exception):
    pass


class PDQueue(object):
    """
    A directory based queue for PagerDuty events.

    Notes:
    - Designed for multiple processes concurrently using the queue.
    - Each entry in the queue is written to a separate file in the
        queue directory.
    - Files are named so that sorting by file name is queue order.
    - Concurrent enqueues use exclusive file create & retries to avoid
        using the same file name.
    - Concurrent dequeues are serialized with an exclusive dequeue lock.
    - A dequeue will hold the exclusive lock until the consume callback
        is done.
    - dequeue never block enqueue, and enqueue never blocks dequeue.
    """

    def __init__(self, queue_dir, lock_class):
        self.queue_dir = queue_dir
        self.lock_class = lock_class

        self._create_queue_dir()
        self._verify_permissions()

        self._dequeue_lockfile = os.path.join(
            self.queue_dir, "dequeue.lock"
            )

    def _create_queue_dir(self):
        if not os.access(self.queue_dir, os.F_OK):
            os.mkdir(self.queue_dir, 0700)

    def _verify_permissions(self):
        if not (os.access(self.queue_dir, os.R_OK)
            and os.access(self.queue_dir, os.W_OK)):
            raise Exception(
                "Can't read/write to directory %s, please check permissions."
                % self.queue_dir
                )

    # Get the list of queued files from the queue directory in enqueue order
    def _queued_files(self, file_prefix="pdq_"):
        fnames = [
            f for f in os.listdir(self.queue_dir) if f.startswith(file_prefix)
            ]
        fnames.sort()
        return fnames

    def _abspath(self, fname):
        return os.path.join(self.queue_dir, fname)

    def enqueue(self, s):
        # write to an exclusive temp file
        _, tmp_fname_abs, tmp_fd = self._open_creat_excl_with_retry(
            "tmp_%d.txt"
            )
        os.write(tmp_fd, s)
        # get an exclusive queue entry file
        pdq_fname, pdq_fname_abs, pdq_fd = self._open_creat_excl_with_retry(
            "pdq_%d.txt"
            )
        # since we're exclusive on both files, we can safely rename
        # the tmp file
        os.fsync(tmp_fd)  # this seems to be the most we can do for durability
        os.close(tmp_fd)
        # would love to fsync the rename but we're not writing a DB :)
        os.rename(tmp_fname_abs, pdq_fname_abs)
        os.close(pdq_fd)

        return pdq_fname

    def _open_creat_excl_with_retry(self, fname_fmt):
        n = 0
        while True:
            t_millisecs = int(time.time() * 1000)
            fname = fname_fmt % t_millisecs
            fname_abs = self._abspath(fname)
            fd = _open_creat_excl(fname_abs)
            if fd is None:
                n += 1
                if n < 100:
                    time.sleep(0.001)
                    continue
                else:
                    raise Exception(
                        "Too many retries! (Last attempted name: %s)"
                        % fname_abs
                        )
            else:
                return fname, fname_abs, fd

    def dequeue(self, consume_func):
        lock = self.lock_class(self._dequeue_lockfile)
        lock.acquire()
        try:
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

            consume_code = consume_func(s)

            if consume_code is EVENT_CONSUMED:
                try:
                    os.remove(fname_abs)
                except IOError as e:
                    # TODO this could lead to duplicate event sends...
                    # TODO use a logger
                    print "Could not delete consumed event file %s: %s" % \
                        (fname, e)
            elif consume_code is EVENT_CONSUME_ERROR:
                try:
                    errname_abs = self._abspath(fname.replace("pdq_", "err_"))
                    os.rename(fname_abs, errname_abs)
                except IOError as e:
                    # TODO use a logger
                    print "Could not rename problematic event file %s: %s" % \
                        (fname, e)
        finally:
            lock.release()

    def cleanup(self, delete_before_sec=86400):
        delete_before_time = (int(time.time()) - delete_before_sec) * 1000

        def _cleanup_files(fname_prefix):
            fnames = self._queued_files(fname_prefix)
            for fname in fnames:
                try:
                    enqueue_time = int(fname.split('.')[0].split('_')[1])
                    if enqueue_time >= delete_before_time:
                        fnames.remove(fname)
                except:
                    # invalid file-name; we'll ignore it.
                    # TODO use a logger.
                    print "Cleanup: ignoring invalid file name %s" % fname
                    fnames.remove(fname)
            for fname in fnames:
                try:
                    os.remove(self._abspath(fname))
                except IOError as e:
                    # TODO use a logger or throw up.
                    print "Could not clean up file %s: %s" % (fname, e)

        # clean up bad / temp files created before delete-before-time.
        _cleanup_files("err_")
        _cleanup_files("tmp_")


def _open_creat_excl(fname_abs):
    try:
        return os.open(fname_abs, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except OSError, e:
        if e.errno == errno.EEXIST:
            return None
        else:
            raise
