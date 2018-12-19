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

import json
import logging
import socket
import time
from urllib2 import HTTPError, Request, URLError

from pdagent.thirdparty import httpswithverify
from pdagent.thirdparty.ssl_match_hostname import CertificateError
from pdagent.constants import ConsumeEvent, EVENTS_API_BASE_V1, SERVICE_KEY_KEY_V1, EVENTS_API_BASE_V2, SERVICE_KEY_KEY_V2
from pdagent.pdqueue import EmptyQueueError
from pdagent.pdthread import RepeatingTask


logger = logging.getLogger(__name__)


class SendEventTask(RepeatingTask):

    def __init__(
            self,
            pd_queue,
            send_interval_secs,
            cleanup_interval_secs,
            cleanup_threshold_secs,
            source_address='0.0.0.0',
            ):
        RepeatingTask.__init__(self, send_interval_secs, False)
        self.pd_queue = pd_queue
        self.cleanup_interval_secs = cleanup_interval_secs
        self.cleanup_threshold_secs = cleanup_threshold_secs
        self.last_cleanup_time = 0
        self._source_address = source_address
        self._urllib2 = httpswithverify  # to ease unit testing.

    def tick(self):
        # flush the event queue.
        logger.debug("Flushing event queue")
        try:
            self.pd_queue.flush(self.send_event, self.is_stop_invoked)
        except EmptyQueueError:
            logger.debug("Nothing to do - queue is empty!")
        except IOError:
            logger.error("I/O error while flushing queue:", exc_info=True)
        except:
            logger.error("Error while flushing queue:", exc_info=True)

        # clean up if required.
        secs_since_cleanup = int(time.time()) - self.last_cleanup_time
        if secs_since_cleanup >= self.cleanup_interval_secs:
            try:
                self.pd_queue.cleanup(self.cleanup_threshold_secs)
            except:
                logger.error("Error while cleaning up queue:", exc_info=True)
            self.last_cleanup_time = int(time.time())

    def send_event(self, json_event_str, event_id):
        # Note that Request here is from urllib2, not self._urllib2.
        # choose api version based on means of ""
        if SERVICE_KEY_KEY_V1 in json_event_str:
            logger.debug("Sending event to V1 Api: ")
            request = Request(EVENTS_API_BASE_V1)
        elif  SERVICE_KEY_KEY_V2 in json_event_str:
            logger.debug("Sending event to V2 Api: ")
            request = Request(EVENTS_API_BASE_V2)
        else: 
            logger.debug("Unknown service key sending to V1 api ")
            request = Request(EVENTS_API_BASE_V1)
            
        request.add_header("Content-type", "application/json")
        request.add_data(json_event_str)

        try:
            response = self._urllib2.urlopen(request,
                source_address=self._source_address)
            status_code = response.getcode()
            result_str = response.read()
            response.close()
        except HTTPError as e:
            # the http error is structured similar to an http response.
            status_code = e.getcode()
            result_str = e.read()
            e.close()
        except CertificateError as e:
            logger.error(
                "Certificate validation error while sending event: %s" % e
                )
            logger.debug("Traceback:", exc_info=True)
            return ConsumeEvent.STOP_ALL
        except socket.timeout as e:
            logger.error("Timeout while sending event: %s" % e)
            logger.debug("Traceback:", exc_info=True)
            # This could be real issue with PD, or just some anomaly in
            # processing this service key or event. We'll retry this
            # service key a few more times, and then decide that this
            # event is possibly a bad entry.
            return ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY
        except URLError as e:
            if isinstance(e.reason, socket.timeout):
                logger.error("Timeout while sending event: %s" % e)
                logger.debug("Traceback:", exc_info=True)
                # see above socket.timeout catch-block for details.
                return ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY
            else:
                logger.error(
                    "Error establishing connection for sending event: %s" % e
                    )
                logger.debug("Traceback:", exc_info=True)
                return ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED
        except:
            logger.error("Error while sending event:", exc_info=True)
            return ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED

        try:
            result = json.loads(result_str)
        except:
            logger.warning(
                "Error reading response data while sending event:",
                exc_info=True
                )
            result = {}
        if result.get("status") == "success":
            logger.info("incident_key = %s", result.get("incident_key"))
        else:
            logger.error(
                "Error sending event %s; Error code: %d, Reason: %s" %
                (event_id, status_code, result_str)
                )

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
            # anything 3xx and >= 600 -- we don't know what this means!!
            return ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED
