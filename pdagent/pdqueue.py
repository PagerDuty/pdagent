import fcntl
import os
import re
import time

class PDQueue(object):
    """
    This class implements a simple directory based queue for PagerDuty events
    """

    QUEUE_DIR = "/tmp/pagerduty"  # TODO changeme

    def __init__(self, queue_dir=QUEUE_DIR):
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

    # Get the list of files from the queue directory
    def _queued_files(self):
        files = os.listdir(self.queue_dir)
        pd_names = re.compile("pd_")
        pd_file_names = filter(pd_names.match, files)

        # We need to sort the files by the timestamp.
        # This function extracts the timestamp out of the file name
        def file_timestamp(file_name):
            return int(re.search('pd_(\d+)_', file_name).group(1))

        sorted_file_names = sorted(pd_file_names, key=file_timestamp)
        return pd_file_names

    def _flush_queue(self):
        from pdagent.pdagentutil import send_event_json_str
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
            finally:
                fcntl.lockf(lock_file.fileno(), fcntl.LOCK_UN)

    def enqueue(self, event_json_str):
        process_id = os.getpid()
        time_seconds = int(time.time())
        file_name = "%s/pd_%d_%d" % (self.queue_dir, time_seconds, process_id)
        with open(file_name, "w", 0600) as f:
            f.write(event_json_str)
