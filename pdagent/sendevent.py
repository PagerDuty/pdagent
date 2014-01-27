
import json
import logging
import socket
import time
from urllib2 import HTTPError, URLError
import urllib2

from pdagent import httpswithverify
from pdagent.backports.ssl_match_hostname import CertificateError
from pdagent.constants import ConsumeEvent, EVENTS_API_BASE
from pdagent.pdqueue import EmptyQueueError
from pdagent.pdthread import RepeatingThread


logger = logging.getLogger(__name__)


class SendEventThread(RepeatingThread):

    def __init__(self, mainConfig, pdQueue, lastCleanupTimeSec):
        RepeatingThread.__init__(self, mainConfig['check_freq_sec'])
        self.mainConfig = mainConfig
        self.pdQueue = pdQueue
        self.lastCleanupTimeSec = lastCleanupTimeSec

    def tick(self):
        # flush the event queue.
        logger.info("Flushing event queue")
        try:
            self.pdQueue.flush(self.send_event)
        except EmptyQueueError:
            logger.info("Nothing to do - queue is empty!")
        except IOError:
            logger.error("I/O error while flushing queue:", exc_info=True)
        except:
            logger.error("Error while flushing queue:", exc_info=True)

        # clean up if required.
        secondsSinceCleanup = int(time.time()) - self.lastCleanupTimeSec
        if secondsSinceCleanup >= self.mainConfig['cleanup_freq_sec']:
            try:
                self.pdQueue.cleanup(self.mainConfig['cleanup_before_sec'])
            except:
                logger.error("Error while cleaning up queue:", exc_info=True)
            self.lastCleanupTimeSec = int(time.time())

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
                # processing this service key or event. We'll retry this service key
                # a few more times, and then decide that this event is possibly a
                # bad entry.
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
            # We'll retry this service key a few times, and then decide that this
            # event is possibly a bad entry.
            return ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY
        else:
            # anything 3xx and >= 5xx
            return ConsumeEvent.NOT_CONSUMED
