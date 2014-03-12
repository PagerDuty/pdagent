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

from httplib import HTTPException
import json
import unittest
from urllib2 import URLError, HTTPError

from pdagent.constants import AGENT_VERSION
from pdagent.heartbeat import HeartbeatTask
from pdagent.thirdparty import httpswithverify
from pdagenttest.mockqueue import MockQueue
from pdagenttest.mockresponse import MockResponse
from pdagenttest.mockurllib import MockUrlLib


AGENT_ID = "test123"
SYSTEM_INFO = {
    "name": "Test",
    "version": "Infinity"
    }
RESPONSE_FREQUENCY_SEC = 30


class HeartbeatTest(unittest.TestCase):

    def new_heartbeat_task(self):
        hb = HeartbeatTask(
            RESPONSE_FREQUENCY_SEC + 10,  # something different from response.
            AGENT_ID,
            self.mock_queue(),
            SYSTEM_INFO
            )
        hb._urllib2 = MockUrlLib()
        return hb

    def mock_queue(self):
        return MockQueue(
            status={"foo": "bar"},
            aggregated=True,
            throttle_info=True
            )

    def test_data(self):
        hb = self.new_heartbeat_task()
        hb.tick()
        expected = {
            "agent_id": AGENT_ID,
            "agent_version": AGENT_VERSION,
            "system_info": SYSTEM_INFO,
            "agent_stats": hb._pd_queue.status
            }
        self.assertEqual(json.loads(hb._urllib2.request.get_data()), expected)

    def test_new_frequency(self):
        hb = self.new_heartbeat_task()
        hb._urllib2.response = MockResponse(
            data=json.dumps({
                "heartbeat_interval_secs": RESPONSE_FREQUENCY_SEC
                })
            )
        hb.tick()
        self.assertEquals(RESPONSE_FREQUENCY_SEC, hb._interval_secs)

    def test_communication_error(self):
        def err_func(url, **kwargs):
            raise Exception
        hb = self.new_heartbeat_task()
        hb._urllib2.urlopen = err_func
        hb.tick()
        # no errors here means communication errors were handled.

    def test_bad_response_data(self):
        hb = self.new_heartbeat_task()
        hb._urllib2.response = MockResponse(data="bad")
        hb.tick()
        # no errors here means bad response data was handled.

    def test_url_connection_error(self):
        def error(*args, **kwargs):
            t.append('e')
            httpswithverify.urlopen("https://localhost/error")
        t = []
        hb = self.new_heartbeat_task()
        hb._urllib2.urlopen = error
        hb.set_interval_secs(100)
        hb._heartbeat_max_retries = 2
        hb.tick()
        self.assertEquals(t, ['e', 'e'])

    def test_retry_vs_no_retry(self):
        def error(*args, **kwargs):
            t.append('e')
            raise e
        hb = self.new_heartbeat_task()
        hb._urllib2.urlopen = error
        hb._retry_gap_secs = 1
        hb.set_interval_secs(100)
        hb._heartbeat_max_retries = 2
        # http non-5xx
        t = []
        e = HTTPError(None, 400, None, None, None)
        hb.tick()
        self.assertEquals(t, ['e'])
        # http 5xx
        t = []
        e = HTTPError(None, 500, None, None, None)
        hb.tick()
        self.assertEquals(t, ['e', 'e'])
        # urlerror
        t = []
        e = URLError("foo")
        hb.tick()
        self.assertEquals(t, ['e', 'e'])
        # httpexception
        t = []
        e = HTTPException()
        hb.tick()
        self.assertEquals(t, ['e', 'e'])

    def test_retry_limits(self):
        def error(*args, **kwargs):
            t.append('e')
            raise URLError(500)
        t = []
        hb = self.new_heartbeat_task()
        hb._urllib2.urlopen = error
        hb._retry_gap_secs = 1
        # max retries
        hb.set_interval_secs(100)
        hb._heartbeat_max_retries = 2
        hb.tick()
        self.assertEquals(t, ['e'] * 2)
        # time limit
        t = []
        hb.set_interval_secs(5)
        hb._heartbeat_max_retries = 10
        hb.tick()
        self.assertEquals(t, ['e'] * 3)

    def test_retry_and_stop_signal(self):
        def error(*args, **kwargs):
            hb.stop_async()
            t.append('e')
            raise URLError(500)
        t = []
        hb = self.new_heartbeat_task()
        hb._urllib2.urlopen = error
        hb.set_interval_secs(100)
        hb._heartbeat_max_retries = 10
        hb._retry_gap_secs = 1
        hb.tick()
        self.assertEquals(t, ['e'])


if __name__ == '__main__':
    unittest.main()
