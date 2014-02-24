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
from urllib2 import Request, URLError, HTTPError

from pdagent.constants import HEARTBEAT_URI
from pdagent.pdthread import RepeatingTask
from pdagent.thirdparty import httpswithverify


logger = logging.getLogger(__name__)


class HeartbeatTask(RepeatingTask):

    def __init__(self, heartbeat_interval_secs, agent_id):
        RepeatingTask.__init__(self, heartbeat_interval_secs, True)
        self.agent_id = agent_id
        self._urllib2 = httpswithverify  # to ease unit testing.

    def tick(self):
        try:
            logger.info("Sending heartbeat")
            # max time is half an interval
            retry_time_limit = time.time() + (self.get_interval_secs() / 2)
            attempt_number = 0
            response_str = None
            heartbeat_json = self._make_heart_beat_json()
            while not self.is_stop_invoked():
                attempt_number += 1
                try:
                    response_str = self._heart_beat(heartbeat_json)
                    break  # yay! success!
                except HTTPError as e:
                    # retry for 5xx errors
                    if 500 <= e.getcode() < 600:
                        logger.error("HTTPError (will retry): %s" % e)
                    else:
                        raise
                except (URLError, IOError):
                    # assumes 2.6 where socket.error is a sub-class of IOError
                    logger.error("Error (will retry):", exc_info=True)
                # retry limit checks
                if time.time() > retry_time_limit:
                    logger.info("Won't retry - time limit reached")
                    break
                if attempt_number > 10:
                    logger.info("Won't retry - count limit reached")
                    break
                # sleep before retry
                logger.debug("Sleeping before retry...")
                for _ in range(10):
                    if self.is_stop_invoked():
                        break
                    time.sleep(1)
                else:
                    logger.debug("Retrying...")
            # if successful, there may be a response body to process
            if response_str:
                self._process_response(response_str)
        except:
            logger.error(
                "Error sending heartbeat (won't retry):",
                exc_info=True
                )

    def _make_heart_beat_json(self):
        return {
            "agent_id": self.agent_id
            }

    def _heart_beat(self, heartbeat_json):
        # Note that Request here is from urllib2, not self._urllib2.
        request = Request(HEARTBEAT_URI)
        request.add_header("Content-type", "application/json")
        phone_home_data = json.dumps(heartbeat_json)
        request.add_data(phone_home_data)
        response = self._urllib2.urlopen(request)
        return response.read()

    def _process_response(self, response_str):
        try:
            result = json.loads(response_str)
        except:
            logger.warning(
                "Error reading heart-beat response data:",
                exc_info=True
                )
        else:
            heartbeat_interval_secs = result.get("heartbeat_interval_secs")
            if heartbeat_interval_secs:
                self.set_interval_secs(heartbeat_interval_secs)
