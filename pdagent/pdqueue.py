import errno
import os
import logging
import time
from constants import EVENT_CONSUMED, EVENT_NOT_CONSUMED, EVENT_BAD_ENTRY, \
    EVENT_STOP_ALL, EVENT_BACKOFF_SVCKEY_BAD_ENTRY, \
    EVENT_BACKOFF_SVCKEY_NOT_CONSUMED


logger = logging.getLogger(__name__)

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

    def __init__(self,
            queue_dir, lock_class, time_calc,
            backoff_secs, backoff_db):
        from pdagentutil import \
            ensure_readable_directory, ensure_writable_directory

        self.queue_dir = queue_dir

        ensure_readable_directory(self.queue_dir)
        ensure_writable_directory(self.queue_dir)

        self.lock_class = lock_class
        self._dequeue_lockfile = os.path.join(
            self.queue_dir, "dequeue.lock"
            )

        # error-handling: back-off related stuff.
        self.backoff_secs = backoff_secs
        self.max_backoff_attempts = len(self.backoff_secs)
        self.backoff_db = backoff_db
        # the time calculator.
        self.time = time_calc

    # Get the list of queued files from the queue directory in enqueue order
    def _queued_files(self, file_prefix="pdq_"):
        fnames = [
            f for f in os.listdir(self.queue_dir) if f.startswith(file_prefix)
            ]
        fnames.sort()
        return fnames

    def _abspath(self, fname):
        return os.path.join(self.queue_dir, fname)

    def enqueue(self, service_key, s):
        # write to an exclusive temp file
        _, tmp_fname_abs, tmp_fd = self._open_creat_excl_with_retry(
            "tmp_%%d_%s.txt" % service_key
            )
        os.write(tmp_fd, s)
        # get an exclusive queue entry file
        pdq_fname, pdq_fname_abs, pdq_fd = self._open_creat_excl_with_retry(
            "pdq_%%d_%s.txt" % service_key
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
            t_millisecs = int(self.time.time() * 1000)
            fname = fname_fmt % t_millisecs
            fname_abs = self._abspath(fname)
            fd = _open_creat_excl(fname_abs)
            if fd is None:
                n += 1
                if n < 100:
                    self.time.sleep(0.001)
                    continue
                else:
                    raise Exception(
                        "Too many retries! (Last attempted name: %s)"
                        % fname_abs
                        )
            else:
                return fname, fname_abs, fd

    def dequeue(self, consume_func):
        # process only first event in queue.
        self._process_queue(lambda events: events[0:1], consume_func)

    def flush(self, consume_func):
        # process all events in queue.
        self._process_queue(lambda events: events, consume_func)

    def _process_queue(self, filter_events_to_process_func, consume_func):
        lock = self.lock_class(self._dequeue_lockfile)
        lock.acquire()

        try:
            prev_backoff_data = None
            try:
                prev_backoff_data = self.backoff_db.get()
            except:
                logger.warning(
                    "Unable to load queue-error back-off history",
                    exc_info=True)
            if not prev_backoff_data:
                # first time, or errors during db read...
                prev_backoff_data = {
                    'attempts': {},
                    'next_retries': {}
                }
            cur_backoff_data = {
                'attempts': {},
                'next_retries': {}
            }
            prev_svc_key_attempt = prev_backoff_data['attempts']
            prev_svc_key_next_retry = prev_backoff_data['next_retries']
            cur_svc_key_attempt = cur_backoff_data['attempts']
            cur_svc_key_next_retry = cur_backoff_data['next_retries']

            file_names = self._queued_files()

            if not len(file_names):
                raise EmptyQueue
            file_names = filter_events_to_process_func(file_names)
            err_svc_keys = set()

            def handle_backoff():
                # don't process more events with same service key.
                err_svc_keys.add(svc_key)
                # has back-off threshold been reached?
                cur_attempt = prev_svc_key_attempt.get(svc_key, 0) + 1
                if cur_attempt > self.max_backoff_attempts:
                    if consume_code == EVENT_BACKOFF_SVCKEY_NOT_CONSUMED:
                        # consume function does not want us to do
                        # anything with the event. We'll still consider this
                        # service key to be erroneous, though, and continue
                        # backing off events in the key.
                        pass
                    elif consume_code == EVENT_BACKOFF_SVCKEY_BAD_ENTRY:
                        self._tag_as_error(fname)
                        # now that we have handled the bad entry, we'll want
                        # to give the other events in this service key a chance,
                        # so don't consider svc key as erroneous.
                        err_svc_keys.remove(svc_key)
                if svc_key in err_svc_keys:
                    # if backoff-seconds have been exhausted, reuse the last one.
                    backoff_index = min(
                        cur_attempt,
                        self.max_backoff_attempts) - 1
                    cur_svc_key_next_retry[svc_key] = int(self.time.time()) + \
                        self.backoff_secs[backoff_index]
                    cur_svc_key_attempt[svc_key] = cur_attempt

            now = self.time.time()
            for fname in file_names:
                _, _, svc_key = _get_event_metadata(fname)
                if prev_svc_key_next_retry.get(svc_key, 0) > now:
                    # not yet time to retry; copy over back-off data.
                    cur_svc_key_attempt[svc_key] = \
                        prev_svc_key_attempt.get(svc_key)
                    cur_svc_key_next_retry[svc_key] = \
                        prev_svc_key_next_retry.get(svc_key)
                elif cur_svc_key_next_retry.get(svc_key, 0) <= now and \
                        svc_key not in err_svc_keys:
                    # nothing has gone wrong in this pass yet.
                    fname_abs = self._abspath(fname)
                    # TODO: handle missing file or other errors
                    f = open(fname_abs)
                    try:
                        s = f.read()
                    finally:
                        f.close()
                    consume_code = consume_func(s)

                    if consume_code == EVENT_CONSUMED:
                        # TODO a failure here will mean duplicate event sends
                        os.remove(fname_abs)
                    elif consume_code == EVENT_NOT_CONSUMED:
                        pass
                    elif consume_code == EVENT_STOP_ALL:
                        # don't process any more events.
                        break
                    elif consume_code == EVENT_BAD_ENTRY:
                        self._tag_as_error(fname)
                    elif consume_code == EVENT_BACKOFF_SVCKEY_BAD_ENTRY or \
                            consume_code == EVENT_BACKOFF_SVCKEY_NOT_CONSUMED:
                        handle_backoff()
                    else:
                        raise ValueError(
                            "Unsupported dequeue consume code %d" %
                            consume_code)

            try:
                # persist back-off info.
                self.backoff_db.set(cur_backoff_data)
            except:
                logger.warning(
                    "Unable to save queue-error back-off history",
                    exc_info=True)
        finally:
            lock.release()

    def resurrect(self, service_key=None):
        # move dead events of given service key back to queue.
        errnames = self._queued_files("err_")
        for errname in errnames:
            if not service_key or \
                    _get_event_metadata(errname)[2] == service_key:
                self._unsafe_untag_as_error(errname)

    def cleanup(self, delete_before_sec):
        delete_before_time = (int(self.time.time()) - delete_before_sec) * 1000

        def _cleanup_files(fname_prefix):
            fnames = self._queued_files(fname_prefix)
            for fname in fnames:
                try:
                    _, enqueue_time, _ = _get_event_metadata(fname)
                except:
                    # invalid file-name; we'll not include it in cleanup.
                    logger.info(
                        "Cleanup: ignoring invalid file name %s" % fname)
                    fnames.remove(fname)
                else:
                    if enqueue_time >= delete_before_time:
                        fnames.remove(fname)
            for fname in fnames:
                try:
                    os.remove(self._abspath(fname))
                except IOError as e:
                    logger.warning(
                        "Could not clean up file %s: %s" % (fname, str(e)))

        # clean up bad / temp files created before delete-before-time.
        _cleanup_files("err_")
        _cleanup_files("tmp_")

    def get_status(self, service_key=None):
        status = {}
        empty_stats = {
            "pending": 0,
            "error": 0
        }
        for fname in self._queued_files():
            svc_key = _get_event_metadata(fname)[2]
            if not service_key or svc_key == service_key:
                if not status.get(svc_key):
                    status[svc_key] = dict(empty_stats)
                status[svc_key]["pending"] += 1
        for errname in self._queued_files("err_"):
            svc_key = _get_event_metadata(errname)[2]
            if not service_key or svc_key == service_key:
                if not status.get(svc_key):
                    status[svc_key] = dict(empty_stats)
                status[svc_key]["error"] += 1
        return status

    def _tag_as_error(self, fname):
        errname = fname.replace("pdq_", "err_")
        fname_abs = self._abspath(fname)
        errname_abs = self._abspath(errname)
        logger.info(
            "Tagging as error: %s -> %s..." %
            (fname, errname))
        os.rename(fname_abs, errname_abs)

    # This function moves error files back into regular files, so ensure that
    # you have considered any concurrency-related consequences to other queue
    # operations before invoking this function.
    def _unsafe_untag_as_error(self, errname):
        fname = errname.replace("err_", "pdq_")
        errname_abs = self._abspath(errname)
        fname_abs = self._abspath(fname)
        logger.info(
            "Untagging as error: %s -> %s..." %
            (errname, fname))
        os.rename(errname_abs, fname_abs)


def _open_creat_excl(fname_abs):
    try:
        return os.open(fname_abs, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except OSError, e:
        if e.errno == errno.EEXIST:
            return None
        else:
            raise

def _get_event_metadata(fname):
    type, enqueue_time_str, service_key = fname.split('.')[0].split('_')
    return type, int(enqueue_time_str), service_key
