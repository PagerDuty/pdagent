
import json
import logging
import socket
import time
from urllib2 import HTTPError, URLError
import urllib2

from pdagent.thirdparty import httpswithverify
from pdagent.thirdparty.ssl_match_hostname import CertificateError
from pdagent.constants import AGENT_VERSION, ConsumeEvent, EVENTS_API_BASE, \
    PHONE_HOME_URI
from pdagent.pdqueue import EmptyQueueError
from pdagent.pdthread import RepeatingThread


logger = logging.getLogger(__name__)


def phone_home(pd_queue, guid, system_stats=None):
    # TODO finalize keys.
    phone_home_data = {
        "agent_id": guid,
        "agent_version": AGENT_VERSION,
        "agent_stats": pd_queue.get_status(throttle_info=True, aggregated=True)
    }
    if system_stats:
        phone_home_data['system_info'] = system_stats

    request = urllib2.Request(PHONE_HOME_URI)
    request.add_header("Content-type", "application/json")
    request.add_data(json.dumps(phone_home_data))
    try:
        response = httpswithverify.urlopen(request)
        result_str = response.read()
    except:
        logger.error("Error while phoning home:", exc_info=True)
        result_str = None

    if result_str:
        try:
            result = json.loads(result_str)
        except:
            logger.warning(
                "Error reading phone-home response data:",
                exc_info=True)
            result = {}

        # TODO store heartbeat frequency.
        result.get("heartbeat_frequency_sec")


class SendEventThread(RepeatingThread):

    def __init__(
            self, pd_queue, check_freq_sec,
            cleanup_freq_sec, cleanup_before_sec,
            guid,
            system_stats,
            ):
        RepeatingThread.__init__(self, check_freq_sec)
        self.pd_queue = pd_queue
        self.cleanup_freq_sec = cleanup_freq_sec
        self.cleanup_before_sec = cleanup_before_sec
        self.guid = guid
        self.system_stats = system_stats
        self.last_cleanup_time = 0

    def tick(self):
        # flush the event queue.
        logger.info("Flushing event queue")
        queue_processed = False
        try:
            self.pd_queue.flush(self.send_event)
            queue_processed = True
        except EmptyQueueError:
            logger.info("Nothing to do - queue is empty!")
        except IOError:
            logger.error("I/O error while flushing queue:", exc_info=True)
        except:
            logger.error("Error while flushing queue:", exc_info=True)

        # clean up if required.
        secs_since_cleanup = int(time.time()) - self.last_cleanup_time
        if secs_since_cleanup >= self.cleanup_freq_sec:
            try:
                self.pd_queue.cleanup(self.cleanup_before_sec)
            except:
                logger.error("Error while cleaning up queue:", exc_info=True)
            self.last_cleanup_time = int(time.time())

        # send phone home information if required.
        # TODO decide about threads for all these features.
        if queue_processed or self.system_stats:
            try:
                # phone home, sending out system info the first time.
                phone_home(self.pd_queue, self.guid, self.system_stats)
                # system stats not sent out after first time
                self.system_stats = None
            except:
                logger.error("Error while phoning home:", exc_info=True)

    def send_event(self, json_event_str):
        request = urllib2.Request(EVENTS_API_BASE)
        request.add_header("Content-type", "application/json")
        request.add_data(json_event_str)

        status_code, result_str = None, None
        try:
            response = httpswithverify.urlopen(
                request,
                timeout=self.mainConfig["send_event_timeout_sec"]
                )
            status_code = response.getcode()
            result_str = response.read()
        except HTTPError as e:
            # the http error is structured similar to an http response.
            status_code = e.getcode()
            result_str = e.read()
        except CertificateError:
            logger.error(
                "Server certificate validation error while sending event:",
                exc_info=True)
            return ConsumeEvent.STOP_ALL
        except URLError as e:
            if isinstance(e.reason, socket.timeout):
                logger.error("Timeout while sending event:", exc_info=True)
                # This could be real issue with PD, or just some anomaly in
                # processing this service key or event. We'll retry this
                # service key a few more times, and then decide that this
                # event is possibly a bad entry.
                return ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY
            else:
                logger.error(
                    "Error establishing a connection for sending event:",
                    exc_info=True)
                return ConsumeEvent.NOT_CONSUMED
        except IOError:
            logger.error("Error while sending event:", exc_info=True)
            return ConsumeEvent.NOT_CONSUMED

        try:
            result = json.loads(result_str)
        except:
            logger.warning(
                "Error reading response data while sending event:",
                exc_info=True)
            result = {}
        if result.get("status") == "success":
            logger.info("incident_key =", result.get("incident_key"))
        else:
            logger.error("Error sending event %s; Error code: %d, Reason: %s" %
                (json_event_str, status_code, result_str))

        if status_code < 300:
            return ConsumeEvent.CONSUMED
        elif status_code == 403:
            # We are getting throttled! We'll retry this service key a few more
            # times, but never consider this event as erroneous.
            return ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED
        elif status_code >= 400 and status_code < 500:
            return ConsumeEvent.BAD_ENTRY
        elif status_code >= 500 and status_code < 600:
            # Hmm. Could be server-side problem, or a bad entry.
            # We'll retry this service key a few times, and then decide that
            # this event is possibly a bad entry.
            return ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY
        else:
            # anything 3xx and >= 5xx
            return ConsumeEvent.NOT_CONSUMED
