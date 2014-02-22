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
import unittest

from pdagent.heartbeat import HeartbeatTask
from pdagenttest.mockqueue import MockQueue
from pdagenttest.mockresponse import MockResponse
from pdagenttest.mockurllib import MockUrlLib


AGENT_ID = "test123"
RESPONSE_FREQUENCY_SEC = 30


class HeartbeatTest(unittest.TestCase):

    def new_heartbeat_task(self):
        ph = HeartbeatTask(
            RESPONSE_FREQUENCY_SEC + 10,  # something different from response.
            AGENT_ID
            )
        ph._urllib2 = MockUrlLib()
        return ph

    def mock_queue(self):
        return MockQueue(
            status={"foo": "bar"},
            aggregated=True,
            throttle_info=True
            )

    def test_data(self):
        ph = self.new_heartbeat_task()
        ph.tick()
        expected = {
            "agent_id": AGENT_ID,
            }
        self.assertEqual(json.loads(ph._urllib2.request.get_data()), expected)

    def test_new_frequency(self):
        ph = self.new_heartbeat_task()
        ph._urllib2.response = MockResponse(
            data=json.dumps({
                "heartbeat_interval_secs": RESPONSE_FREQUENCY_SEC
                })
            )
        ph.tick()
        self.assertEquals(RESPONSE_FREQUENCY_SEC, ph._interval_secs)

    def test_communication_error(self):
        def err_func(url, **kwargs):
            raise Exception
        ph = self.new_heartbeat_task()
        ph._urllib2.urlopen = err_func
        ph.tick()
        # no errors here means communication errors were handled.

    def test_bad_response_data(self):
        ph = self.new_heartbeat_task()
        ph._urllib2.response = MockResponse(data="bad")
        ph.tick()
        # no errors here means bad response data was handled.


if __name__ == '__main__':
    unittest.main()
