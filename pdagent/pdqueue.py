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

    def __init__(self, queue_dir):
        self.queue_dir = queue_dir
        self._create_queue_dir()
        self._verify_permissions()

    def _create_queue_dir(self):
        if not os.access(self.queue_dir, os.F_OK):
            os.mkdir(self.queue_dir, 0700)

    def _verify_permissions(self):
        if not (os.access(self.queue_dir, os.R_OK)
            and os.access(self.queue_dir, os.W_OK)):
            raise Exception("Can't read/write to directory %s, please check permissions." % self.queue_dir)

    def _readfile(self, fname):
        fname_abs = os.path.join(self.queue_dir, fname)
        f = open(fname_abs)
        try:
            return f.read()
        finally:
            f.close()

    # Get the list of queued files from the queue directory
    def _queued_files(self):
        fnames = [f for f in os.listdir(self.queue_dir) if f.startswith("pd_")]
        fnames.sort()
        return fnames

    def _flush_queue(self):
        file_names = self._queued_files()
        # TODO handle related incidents e.g. if there is an ack for which a resolve is also present
        for file_name in file_names:
            file_path = ("%s/%s" % (self.queue_dir, file_name))
            json_event_str = None
            with open(file_path, "r") as event_file:
                json_event_str = event_file.read()
            incident_key, status_code = send_event_json_str(json_event_str)

            # clean up the file only if we are successful, or if the failure was server-side.
            if not (status_code >= 500 and status_code < 600): # success, or non-server-side problem
                os.remove(file_path)

    def flush(self):
        with open("%s/lockfile" % self.queue_dir, "w") as lock_file:
            try:
                fcntl.lockf(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # We have acquired the lock here; let's flush the queue
                self._flush_queue()
            except IOError as e:
                print "Error while trying to acquire lock on queue: %s" % str(e)
            finally:
                fcntl.lockf(lock_file.fileno(), fcntl.LOCK_UN)

    def enqueue(self, event_json_str):
        process_id = os.getpid()
        time_seconds = int(time.time())
        fname = "pd_%d_%d" % (time_seconds, process_id)
        fname_abs = os.path.join(self.queue_dir, fname)
        if os.path.exists(fname_abs):
            raise AssertionError, "Queue entry file already exists: %s" % fname_abs
        with open(fname_abs, "w", 0600) as f:
            f.write(event_json_str)
        return fname

    def dequeue(self, consume_func):
        # TODO: queue read lock
        file_names = self._queued_files()
        if not len(file_names):
            raise EmptyQueue
        fname = file_names[0]
        fname_abs = os.path.join(self.queue_dir, fname)
        # TODO: handle missing file or other errors
        json_event_str = open(fname_abs).read()
        #
        consumed = consume_func(json_event_str)
        #
        if consumed:
            # TODO: handle/log delete error!
            os.remove(fname_abs)

