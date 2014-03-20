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
"""
A directory based queue for PagerDuty events.

Consists of two classes:
- PDQEnqueuer which provides only enqueue functionality.
- PDQueue which provides dequeue and queue management functionality.

Notes:
- Designed for multiple processes concurrently using the queue.
- Each entry in the queue is written to a separate file in the
    queue directory.
- Files are named so that sorting by file name is queue order.
- Concurrent enqueues use exclusive file create and retries to avoid
    using the same file name.
- Concurrent dequeues are serialized with an exclusive dequeue lock.
- A dequeue will hold the exclusive lock until the consume callback
    is done.
- dequeue never block enqueue, and enqueue never blocks dequeue.
"""


import errno
import logging
import os

from constants import ConsumeEvent
from pdagentutil import ensure_readable_directory, ensure_writable_directory, \
    utcnow_isoformat


logger = logging.getLogger(__name__)


class EmptyQueueError(Exception):
    pass


class PDQueueBase(object):

    def __init__(self, queue_dir, lock_class, time_calc):
        self.queue_dir = queue_dir
        self.lock_class = lock_class
        self.time = time_calc

    def _abspath(self, fname):
        return os.path.join(self.queue_dir, fname)


class PDQEnqueuer(PDQueueBase):

    def __init__(
            self,
            queue_dir,
            lock_class,
            time_calc,
            enqueue_file_mode
            ):
        PDQueueBase.__init__(self, queue_dir, lock_class, time_calc)
        self.enqueue_file_mode = enqueue_file_mode

        # Enqueue needs only write access to the directory
        ensure_writable_directory(self.queue_dir)

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
            fd = _open_creat_excl(fname_abs, self.enqueue_file_mode)
            if fd is None:
                n += 1
                if n >= 100:
                    raise Exception(
                        "Too many retries! (Last attempted name: %s)"
                        % fname_abs
                        )
            else:
                return fname, fname_abs, fd


class PDQueue(PDQueueBase):

    def __init__(
            self,
            queue_dir,
            lock_class,
            time_calc,
            event_size_max_bytes,
            backoff_interval,
            max_error_backoffs,
            backoff_db,
            counter_db
            ):
        PDQueueBase.__init__(self, queue_dir, lock_class, time_calc)

        ensure_readable_directory(self.queue_dir)
        ensure_writable_directory(self.queue_dir)

        self._dequeue_lockfile = os.path.join(
            self.queue_dir, "dequeue.lock"
            )

        self.event_size_max_bytes = event_size_max_bytes
        self.backoff_info = _BackoffInfo(
            backoff_db,
            backoff_interval,
            max_error_backoffs,
            time_calc
            )
        self.counter_info = _CounterInfo(counter_db, time_calc)

    # Get the list of queued files from the queue directory in enqueue order
    def _queued_files(self, file_prefix="pdq_"):
        fnames = [
            f for f in os.listdir(self.queue_dir) if f.startswith(file_prefix)
            ]
        fnames.sort()
        return fnames

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
            should_stop_func
            ):
        lock = self.lock_class(self._dequeue_lockfile)
        lock.acquire()

        try:
            file_names = self._queued_files()
            if not len(file_names):
                raise EmptyQueueError

            file_names = filter_events_to_process_func(file_names)
            if not len(file_names):
                return

            now = self.time.time()
            err_svc_keys = set()

            self.backoff_info.update()
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
            self.counter_info.store()
        finally:
            lock.release()

    # Returns true if processing can continue for service key, false if not.
    def _process_event(self, fname, consume_func, svc_key):
        fname_abs = self._abspath(fname)
        data = None
        if not os.path.getsize(fname_abs) > self.event_size_max_bytes:
            with open(self._abspath(fname_abs)) as f:
                data = f.read()

        # ensure that the event is not too large.
        if data is None or len(data) > self.event_size_max_bytes:
            logger.info(
                "Not processing event %s -- it exceeds max-allowed size" %
                fname)
            self._unsafe_change_event_type(fname, 'pdq_', 'err_')
            self.counter_info.increment_failure()
            return True

        logger.info("Processing event " + fname)
        consume_code = consume_func(data, fname)

        if consume_code == ConsumeEvent.CONSUMED:
            # a failure here means duplicate event sends if the incident key
            # was not specified, i.e. if event was enqueued in a non-standard
            # manner (e.g. not using the pd* scripts.)
            self._unsafe_change_event_type(fname, 'pdq_', 'suc_')
            self.counter_info.increment_success()
            return True
        elif consume_code == ConsumeEvent.STOP_ALL:
            # stop processing any more events.
            raise StopIteration
        elif consume_code == ConsumeEvent.BAD_ENTRY:
            self._unsafe_change_event_type(fname, 'pdq_', 'err_')
            self.counter_info.increment_failure()
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
                    svc_key
                    )
                self._unsafe_change_event_type(fname, 'pdq_', 'err_')
                self.counter_info.increment_failure()
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

    def get_stats(
            self,
            detailed_snapshot=False
            ):
        """
        Returns status of events. Status consists of snapshot stats (based on
        current queue state), and historical stats (based on persisted state.)

        Sample data returned:
        {
            "snapshot": {
                "pending_events": {
                    "count": 3,
                    "newest_age_secs": 15,
                    "oldest_age_secs": 40,
                    "service_keys_count": 2
                },
                "succeeded_events": {
                    "count": 3,
                    "newest_age_secs": 5,
                    "oldest_age_secs": 35,
                    "service_keys_count": 2
                },
                "failed_events": {
                    "count": 3,
                    "newest_age_secs": 25,
                    "oldest_age_secs": 45,
                    "service_keys_count": 2
                },
                "throttled_service_keys_count": 1
            },
            "aggregate": {
                "successful_events_count": 20,
                "failed_events_count": 2,
                "started_on": "2014-03-18T20:49:02Z"
            }
        }
        """
        now = self.time.time()

        snapshot_stats = dict()

        def add_stat(queue_file_prefix, stat_name):
            if stat_name not in snapshot_stats:
                snapshot_stats[stat_name] = SnapshotStats(now)
            for fname in self._queued_files(queue_file_prefix):
                snapshot_stats[stat_name].add_event(_get_event_metadata(fname))

        add_stat("pdq_", "pending_events")
        if detailed_snapshot:
            add_stat("suc_", "succeeded_events")
            add_stat("err_", "failed_events")

        for stat_name in snapshot_stats:
            snapshot_stats[stat_name] = snapshot_stats[stat_name].to_dict()

        # if throttle info is required, compute from pre-loaded info.
        # (we don't want to reload info if queue processing is underway.)
        if self.backoff_info._current_retry_at:
            throttled_keys = set()
            now = int(self.time.time())
            for key, retry_at in \
                    self.backoff_info._current_retry_at.iteritems():
                if retry_at > now:
                    throttled_keys.add(key)
            snapshot_stats["throttled_service_keys_count"] = len(throttled_keys)

        stats = {
            "snapshot": snapshot_stats
            }

        # historical counter data for completed events (success, failure)
        if self.counter_info._data:
            stats["aggregate"] = self.counter_info._data

        return stats

    # This function can move error files back into regular files, so ensure that
    # you have considered any concurrency-related consequences to other queue
    # operations before invoking this function.
    def _unsafe_change_event_type(self, event_name, frm, to):
        new_event_name = event_name.replace(frm, to)
        logger.info("Changing %s -> %s..." % (event_name, new_event_name))
        old_abs = self._abspath(event_name)
        new_abs = self._abspath(new_event_name)
        os.rename(old_abs, new_abs)


def _open_creat_excl(fname_abs, mode):
    try:
        return os.open(fname_abs, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except OSError, e:
        if e.errno == errno.EEXIST:
            return None
        else:
            raise


def _get_event_metadata(fname):
    event_type, enqueue_time_str, service_key = \
        fname.split('.')[0].split('_', 2)
    return event_type, int(enqueue_time_str), service_key


class _BackoffInfo(object):
    """
    Loads, accesses, modifies and saves back-off info for
    service keys in queue.
    """

    def __init__(
            self,
            backoff_db,
            backoff_interval,
            max_backoff_attempts,
            time_calc
            ):
        self._db = backoff_db
        self._backoff_interval = backoff_interval
        self._max_backoff_attempts = max_backoff_attempts
        self._time = time_calc
        try:
            data = self._db.get()
        except:
            logger.warning(
                "Unable to load service-key back-off history",
                exc_info=True
                )
            data = None
        if not data:
            # no db yet, or errors during db read.
            data = {
                'attempts': {},
                'next_retries': {}
                }
        self._previous_attempts = {}
        self._current_attempts = data['attempts']
        self._current_retry_at = data['next_retries']
        self.update()

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
    # Note that this doesn't check for threshold breach because the threshold is
    # not required for all situations (e.g. back off due to throttling.)
    def increment(self, svc_key):
        logger.info(
            "Retrying events in service key %s after %d sec" %
            (svc_key, self._backoff_interval)
            )

        self._current_attempts[svc_key] = \
            self._previous_attempts.get(svc_key, 0) + 1
        self._current_retry_at[svc_key] = int(
            self._time.time() + self._backoff_interval
            )

    # only retains data that is still valid at current time.
    def update(self):
        time_now = self._time.time()
        new_attempts = {}
        new_retry_at = {}

        # copy over all still-unexpired current back-offs to new data.
        for (svc_key, retry_at) in self._current_retry_at.iteritems():
            if retry_at > time_now:
                new_attempts[svc_key] = self._current_attempts.get(svc_key)
                new_retry_at[svc_key] = retry_at

        # we'll still hold on to previous attempts data so we can use it to
        # compute new current data if required later.
        self._previous_attempts = self._current_attempts
        self._current_attempts = new_attempts
        self._current_retry_at = new_retry_at

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



class _CounterInfo(object):
    """
    Loads, accesses, modifies and saves counters for processed events.
    """

    def __init__(self, counter_db, time_calc):
        self._db = counter_db
        self._data = {}
        self._time = time_calc

        # try to load data.
        try:
            self._data = self._db.get()
        except:
            logger.error("Unable to load counter history", exc_info=True)
        if not self._data:
            self._reset_data()

        # validate that counter values are indeed integers. If not, reset data.
        for key in (k for k in self._data if k != "started_on"):
            if type(self._data[key]) is not int:
                logger.error(
                    "Invalid counter value %s=%s" % (key, self._data[key])
                    )
                logger.warning("Resetting counter history")
                self._reset_data()

        # Try to persist loaded data. If we can't persist, we'll want to reset
        # the data because we don't know for how long we haven't been able to
        # persist. Instead of updating the currently-loaded old counters,
        # potentially resulting in incorrect values, we'll just consider the
        # persisted data invalid.
        self.store(reset_data_if_failed=True)

    # increments success count by 1.
    def increment_success(self):
        self._increment("successful_events_count")

    # increments failure count by 1.
    def increment_failure(self):
        self._increment("failed_events_count")

    # increments count of given type by 1.
    def _increment(self, counter_type):
        self._data[counter_type] = self._data.get(counter_type, 0) + 1

    # persists current counter history.
    def store(self, reset_data_if_failed=False):
        try:
            self._db.set(self._data)
        except:
            logger.error("Unable to save counter history", exc_info=True)
            if reset_data_if_failed:
                logger.warning("Resetting counter history")
                self._reset_data()

    def _reset_data(self):
        self._data = {
            "started_on": utcnow_isoformat(self._time)
            }


class SnapshotStats(object):
    """
    Stats based on snapshot of queue.
    """
    def __init__(self, time_now):
        self.count = 0
        self.oldest_enqueue_time = None
        self.newest_enqueue_time = None
        self.service_keys = set()
        self._time_now = time_now

    def add_event(self, event_metadata):
        _, enqueue_time, svc_key = event_metadata

        self.count += 1
        if (not self.oldest_enqueue_time) or \
                enqueue_time < self.oldest_enqueue_time:
            self.oldest_enqueue_time = enqueue_time
        if (not self.newest_enqueue_time) or \
                enqueue_time > self.newest_enqueue_time:
            self.newest_enqueue_time = enqueue_time

        self.service_keys.add(svc_key)

    def to_dict(self):
        if self.count:
            return {
                "count": self.count,
                "oldest_age_secs": int(
                    self._time_now - self.oldest_enqueue_time / 1000
                    ),
                "newest_age_secs": int(
                    self._time_now - self.newest_enqueue_time / 1000
                    ),
                "service_keys_count": len(self.service_keys)
                }
        else:
            return {
                "count": self.count
                }
