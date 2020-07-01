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
import time

import pdagent
from pdagent import http
from pdagent.constants import HEARTBEAT_URI
from pdagent.pdthread import RepeatingTask
from pdagent.thirdparty.six.moves.http_client import HTTPException
from pdagent.thirdparty.six.moves.urllib.request import Request
from pdagent.thirdparty.six.moves.urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)


RETRY_GAP_SECS = 10
HEARTBEAT_MAX_RETRIES = 10


class HeartbeatTask(RepeatingTask):

    def __init__(
            self,
            heartbeat_interval_secs,
            agent_id,
            pd_queue,
            system_info,
            source_address='0.0.0.0',
            ):
        RepeatingTask.__init__(self, heartbeat_interval_secs, True)
        self._agent_id = agent_id
        self._pd_queue = pd_queue
        self._system_info = system_info
        # The following variables exist to ease unit testing:
        self._source_address = source_address
        self._urllib2 = http
        self._retry_gap_secs = RETRY_GAP_SECS
        self._heartbeat_max_retries = HEARTBEAT_MAX_RETRIES

    def tick(self):
        try:
            logger.debug("Sending heartbeat")
            # max time is half an interval
            retry_time_limit = time.time() + (self.get_interval_secs() // 2)
            attempt_number = 0
            while not self.is_stop_invoked():
                attempt_number += 1
                try:
                    heartbeat_data = self._make_heartbeat_data()
                    response_str = self._heartbeat(heartbeat_data)
                    logger.debug("Heartbeat successful!")
                    self._system_info = None  # only send in first heartbeat.
                    if response_str:
                        self._process_response(response_str)
                    break
                except HTTPError as e:
                    # retry for 5xx errors
                    if 500 <= e.getcode() < 600:
                        logger.error(
                            "HTTPError sending heartbeat (will retry): %s" % e
                            )
                    else:
                        error = HTTPError(e.url, e.code, e.msg, e.hdrs, None)
                        raise error
                except (URLError, HTTPException) as e:
                    # assumes 2.6 where socket.error is a sub-class of IOError
                    # FIXME: not catching IOError so what does the above mean?
                    logger.error(
                        "Error sending heartbeat (will retry): %s" % e
                        )
                    logger.debug("Traceback:", exc_info=True)
                # retry limit checks
                if time.time() > retry_time_limit:
                    logger.info("Won't retry - time limit reached")
                    break
                if attempt_number >= self._heartbeat_max_retries:
                    logger.info("Won't retry - attempt count limit reached")
                    break
                # sleep before retry
                logger.debug("Sleeping before retry...")
                for _ in range(self._retry_gap_secs):
                    if self.is_stop_invoked():
                        break
                    time.sleep(1)
                else:
                    logger.debug("Retrying...")
        except:
            logger.error(
                "Error sending heartbeat (won't retry):",
                exc_info=True
                )

    def _make_heartbeat_data(self):
        hb_data = {
            "agent_id": self._agent_id,
            "agent_version": pdagent.__version__,
            "agent_stats": self._pd_queue.get_stats()
            }
        if self._system_info:
            hb_data["system_info"] = self._system_info
        return hb_data

    def _heartbeat(self, heartbeat_data):
        # Note that Request here is from urllib2, not self._urllib2.
        request = Request(HEARTBEAT_URI)
        request.add_header("Content-Type", "application/json")
        heartbeat_json_str = json.dumps(heartbeat_data).encode()
        request.data = heartbeat_json_str
        response = self._urllib2.urlopen(request,
            source_address=self._source_address)
        response_str = response.read()
        response.close()
        return response_str

    def _process_response(self, response_str):
        try:
            result = json.loads(response_str)
        except:
            logger.warning(
                "Error reading heartbeat response data:",
                exc_info=True
                )
        else:
            heartbeat_interval_secs = result.get("heartbeat_interval_secs")
            if heartbeat_interval_secs:
                self.set_interval_secs(heartbeat_interval_secs)
