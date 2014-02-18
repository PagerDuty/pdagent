import errno
import os
import logging
from constants import ConsumeEvent


logger = logging.getLogger(__name__)


class EmptyQueueError(Exception):
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

    def __init__(
            self,
            queue_dir, lock_class, time_calc, max_event_bytes,
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

        self.max_event_bytes = max_event_bytes
        self.time = time_calc
        if backoff_db and backoff_secs:
            self.backoff_info = \
                _BackoffInfo(backoff_db, backoff_secs, time_calc)

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
        t_millisecs = int(self.time.time() * 1000)
        while True:
            fname = fname_fmt % (t_millisecs + n)
            fname_abs = self._abspath(fname)
            fd = _open_creat_excl(fname_abs)
            if fd is None:
                n += 1
                if n >= 100:
                    raise Exception(
                        "Too many retries! (Last attempted name: %s)"
                        % fname_abs
                        )
            else:
                return fname, fname_abs, fd

    def dequeue(self, consume_func, stop_check_func=lambda: False):
        # process only first event in queue.
        self._process_queue(
            lambda events: events[0:1],
            consume_func,
            stop_check_func
            )

    def flush(self, consume_func, stop_check_func):
        # process all events in queue.
        self._process_queue(
            lambda events: events,
            consume_func,
            stop_check_func
            )

    def _process_queue(
            self,
            filter_events_to_process_func,
            consume_func,
            should_stop_func):
        lock = self.lock_class(self._dequeue_lockfile)
        lock.acquire()

        try:
            file_names = self._queued_files()
            if not len(file_names):
                raise EmptyQueueError

            file_names = filter_events_to_process_func(file_names)
            if not len(file_names):
                return

            # reload back-off info, in case there are external changes to it.
            now = self.time.time()
            self.backoff_info.load(now)
            err_svc_keys = set()

            for fname in file_names:
                if should_stop_func():
                    break
                _, _, svc_key = _get_event_metadata(fname)
                if svc_key not in err_svc_keys and \
                        self.backoff_info.get_current_retry_at(svc_key) <= now:
                    # no back-off; nothing has gone wrong in this pass yet.
                    try:
                        if not self._process_event(
                            fname, consume_func, svc_key
                        ):
                            # this service key is problematic.
                            err_svc_keys.add(svc_key)
                    except StopIteration:
                        # no further processing must be done.
                        logger.info("Not processing any more events this time")
                        break

            self.backoff_info.store()
        finally:
            lock.release()

    # Returns true if processing can continue for service key, false if not.
    def _process_event(self, fname, consume_func, svc_key):
        # TODO: handle missing file or other errors
        f = open(self._abspath(fname))
        try:
            data = f.read()
        finally:
            f.close()

        # ensure that the event is not too large.
        if len(data) > self.max_event_bytes:
            logger.info(
                "Not processing event %s -- it exceeds max-allowed size" %
                fname)
            self._unsafe_change_event_type(fname, 'pdq_', 'err_')
            return True

        logger.info("Processing event " + fname)
        consume_code = consume_func(data)

        if consume_code == ConsumeEvent.CONSUMED:
            # TODO a failure here means duplicate event sends
            self._unsafe_change_event_type(fname, 'pdq_', 'suc_')
            return True
        elif consume_code == ConsumeEvent.NOT_CONSUMED:
            return True
        elif consume_code == ConsumeEvent.STOP_ALL:
            # stop processing any more events.
            raise StopIteration
        elif consume_code == ConsumeEvent.BAD_ENTRY:
            self._unsafe_change_event_type(fname, 'pdq_', 'err_')
            return True
        elif consume_code == ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY:
            logger.info("Backing off service key " + svc_key)
            if self.backoff_info.is_threshold_breached(svc_key):
                # time for stricter action -- mark event as bad.
                logger.info(
                    (
                        "Service key %s breached back-off limit." +
                        " Assuming bad event."
                    ) %
                    svc_key)
                self._unsafe_change_event_type(fname, 'pdq_', 'err_')
                # now that we have handled the bad entry, we'll want to
                # give the other events in this service key a chance, so
                # don't consider key as erroneous.
                return True
            else:
                self.backoff_info.increment(svc_key)
                return False
        elif consume_code == ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED:
            self.backoff_info.increment(svc_key)
            return False
        else:
            raise ValueError(
                "Unsupported dequeue consume code %d" %
                consume_code)

    def resurrect(self, service_key=None):
        # move dead events of given service key back to queue.
        errnames = self._queued_files("err_")
        for errname in errnames:
            if not service_key or \
                    _get_event_metadata(errname)[2] == service_key:
                self._unsafe_change_event_type(errname, 'err_', 'pdq_')

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
                    if enqueue_time < delete_before_time:
                        try:
                            logger.info("Cleanup: removing file %s" % fname)
                            os.remove(self._abspath(fname))
                        except IOError as e:
                            logger.warning(
                                "Could not clean up file %s: %s" %
                                (fname, str(e))
                                )

        # clean up bad / temp / success files created before delete-before-time.
        _cleanup_files("err_")
        _cleanup_files("tmp_")
        _cleanup_files("suc_")

    def get_status(
        self, service_key=None, aggregated=False, throttle_info=False
    ):
        empty_event_stats = {
            "pending": 0,
            "succeeded": 0,
            "failed": 0
        }
        if aggregated:
            event_stats = empty_event_stats
        else:
            # stats per service-key
            event_stats = {}
        svc_keys = set()

        def add_stat(queue_file_prefix, stat_type):
            for fname in self._queued_files(queue_file_prefix):
                _, _, svc_key = _get_event_metadata(fname)
                if not service_key or (svc_key == service_key):
                    svc_keys.add(svc_key)
                    if aggregated:
                        stats = event_stats
                    else:
                        if not event_stats.get(svc_key):
                            event_stats[svc_key] = dict(empty_event_stats)
                        stats = event_stats[svc_key]
                    stats[stat_type] += 1
        add_stat("pdq_", "pending")
        add_stat("suc_", "succeeded")
        add_stat("err_", "failed")

        status = {
            "service_keys": len(svc_keys),
        }
        if aggregated:
            status.update({
                "events_pending": event_stats["pending"],
                "events_succeeded": event_stats["succeeded"],
                "events_failed": event_stats["failed"]
            })
        else:
            status["events"] = event_stats

        # if throttle info is required, compute from pre-loaded info.
        # (we don't want to reload info if queue processing is underway.)
        if throttle_info and \
                self.backoff_info and \
                self.backoff_info._current_retry_at:
            throttled_keys = set()
            now = int(self.time.time())
            for key, retry_at in \
                    self.backoff_info._current_retry_at.iteritems():
                if (not service_key or (key == service_key)) and \
                        retry_at > now:
                    throttled_keys.add(key)
            status["service_keys_throttled"] = len(throttled_keys)

        return status

    # This function can move error files back into regular files, so ensure that
    # you have considered any concurrency-related consequences to other queue
    # operations before invoking this function.
    def _unsafe_change_event_type(self, event_name, frm, to):
        new_event_name = event_name.replace(frm, to)
        logger.info("Changing %s -> %s..." % (event_name, new_event_name))
        old_abs = self._abspath(event_name)
        new_abs = self._abspath(new_event_name)
        os.rename(old_abs, new_abs)


def _open_creat_excl(fname_abs):
    try:
        return os.open(fname_abs, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except OSError, e:
        if e.errno == errno.EEXIST:
            return None
        else:
            raise


def _get_event_metadata(fname):
    event_type, enqueue_time_str, service_key = fname.split('.')[0].split('_')
    return event_type, int(enqueue_time_str), service_key


class _BackoffInfo(object):
    """
    Loads, accesses, modifies and saves back-off info for
    service keys in queue.
    """

    def __init__(self, backoff_db, backoff_secs, time_calc):
        self._db = backoff_db
        self._backoff_secs = backoff_secs
        self._max_backoff_attempts = len(backoff_secs)
        self._time = time_calc
        self._previous_attempts = {}
        self._current_attempts = {}
        self._current_retry_at = {}

    # returns true if `current-attempts`, or `previous-attempts + 1`,
    # results in a threshold breach.
    def is_threshold_breached(self, svc_key):
        cur_attempt = self._current_attempts.get(
            svc_key,
            self._previous_attempts.get(svc_key, 0) + 1)
        return cur_attempt > self._max_backoff_attempts

    # returns the current retry-at time for svc_key, or 0 if not available.
    def get_current_retry_at(self, svc_key):
        return self._current_retry_at.get(svc_key, 0)

    # updates current attempt and retry data based on previous data.
    def increment(self, svc_key):
        cur_attempt = self._previous_attempts.get(svc_key, 0) + 1
        # if backoff-seconds have been exhausted, reuse the last one.
        backoff_index = min(cur_attempt, self._max_backoff_attempts) - 1
        backoff = self._backoff_secs[backoff_index]
        logger.info(
            "Retrying events in service key %s after %d sec" %
            (svc_key, backoff)
        )

        self._current_attempts[svc_key] = cur_attempt
        self._current_retry_at[svc_key] = int(self._time.time()) + backoff

    # loads data; copies over data that is still valid at time_now to current.
    def load(self, time_now):
        try:
            previous = self._db.get()
        except:
            logger.warning(
                "Unable to load service-key back-off history",
                exc_info=True
                )
            previous = None
        if not previous:
            # no db yet, or errors during db read
            previous = {
                'attempts': {},
                'next_retries': {}
            }

        self._current_attempts = {}
        self._current_retry_at = {}

        # we'll still hold on to previous attempts data so we can use it to
        # compute new current data if required later.
        self._previous_attempts = previous['attempts']

        # copy over all still-unexpired previous back-offs to current data.
        for (svc_key, retry_at) in previous['next_retries'].iteritems():
            if retry_at > time_now:
                self._current_attempts[svc_key] = \
                    self._previous_attempts.get(svc_key)
                self._current_retry_at[svc_key] = retry_at

    # persists current back-off info.
    def store(self):
        try:
            self._db.set({
                'attempts': self._current_attempts,
                'next_retries': self._current_retry_at
            })
        except:
            logger.warning(
                "Unable to save service-key back-off history",
                exc_info=True)
