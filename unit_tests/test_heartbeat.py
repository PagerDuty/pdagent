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
import unittest
from mock import Mock

import pdagent.heartbeat
from pdagent import http
from pdagent.thirdparty.six.moves.urllib.error import URLError, HTTPError
from pdagent.thirdparty.six.moves.http_client import HTTPException
from unit_tests.mockqueue import MockQueue
from unit_tests.mockurllib import MockUrlLib
from unit_tests.mockresponse import MockResponse


logging.basicConfig(level=logging.CRITICAL)

AGENT_ID = "test123"
SYSTEM_INFO = {
    "name": "Test",
    "version": "Infinity"
}
RESPONSE_FREQUENCY_SEC = 30


class HeartbeatTest(unittest.TestCase):

    def new_heartbeat_task(self, source_address='0.0.0.0', gap_secs=10, interval_secs=RESPONSE_FREQUENCY_SEC + 10,
                           max_retries=10):
        hb = pdagent.heartbeat.HeartbeatTask(
            interval_secs,  # something different from response.
            AGENT_ID,
            self.mock_queue(),
            SYSTEM_INFO,
            source_address
        )
        hb._urllib2 = MockUrlLib()
        hb._retry_gap_secs = gap_secs
        hb.set_interval_secs(interval_secs)
        hb._heartbeat_max_retries = max_retries
        return hb

    def mock_queue(self):
        return MockQueue(
            status={"foo": "bar"},
            detailed_snapshot=False
        )

    def test_source_address_and_data(self):
        hb = self.new_heartbeat_task('127.0.0.1')
        hb.tick()
        expected = {
            "agent_id": AGENT_ID,
            "agent_version": pdagent.__version__,
            "system_info": SYSTEM_INFO,
            "agent_stats": hb._pd_queue.status
        }
        self.assertEqual(json.loads(hb._urllib2.request.data), expected)

    def test_data(self):
        hb = self.new_heartbeat_task()
        hb.tick()
        expected = {
            "agent_id": AGENT_ID,
            "agent_version": pdagent.__version__,
            "system_info": SYSTEM_INFO,
            "agent_stats": hb._pd_queue.status
        }
        self.assertEqual(json.loads(hb._urllib2.request.data), expected)

    def test_new_frequency(self):
        hb = self.new_heartbeat_task()
        hb._urllib2.response = MockResponse(
            data=json.dumps({
                "heartbeat_interval_secs": RESPONSE_FREQUENCY_SEC
            })
        )
        hb.tick()
        self.assertEqual(RESPONSE_FREQUENCY_SEC, hb._interval_secs)

    def test_communication_error(self):
        hb = self.new_heartbeat_task()
        hb._urllib2.urlopen = Mock(side_effect=Exception())
        hb.tick()
        # no errors here means communication errors were handled.

    def test_bad_response_data(self):
        hb = self.new_heartbeat_task()
        hb._urllib2.response = MockResponse(data="bad")
        hb.tick()
        # no errors here means bad response data was handled.

    def test_url_connection_error(self):
        def side_effect(*args, **kwargs):
            http.urlopen("https://localhost/error")

        hb = self.new_heartbeat_task(interval_secs=100, max_retries=2)
        mock_error = Mock(side_effect=side_effect)
        hb._urllib2.urlopen = mock_error
        hb.tick()
        self.assertEqual(mock_error.call_count, 2)

    def test_retry_non_5xx(self):
        hb = self.new_heartbeat_task(gap_secs=1, interval_secs=100, max_retries=2)
        mock_error = Mock(side_effect=HTTPError(None, 400, None, None, None))
        hb._urllib2.urlopen = mock_error
        hb.tick()
        self.assertEqual(mock_error.call_count, 1)

    def test_retry_5xx(self):
        hb = self.new_heartbeat_task(gap_secs=1, interval_secs=100, max_retries=2)
        mock_error = Mock(side_effect=HTTPError(None, 500, None, None, None))
        hb._urllib2.urlopen = mock_error
        hb.tick()
        self.assertEqual(mock_error.call_count, 2)

    def test_retry_url_error(self):
        hb = self.new_heartbeat_task(gap_secs=1, interval_secs=100, max_retries=2)
        mock_error = Mock(side_effect=URLError("foo"))
        hb._urllib2.urlopen = mock_error
        hb.tick()
        self.assertEqual(mock_error.call_count, 2)

    def test_retry_http_exception(self):
        hb = self.new_heartbeat_task(gap_secs=1, interval_secs=100, max_retries=2)
        mock_error = Mock(side_effect=HTTPException())
        hb._urllib2.urlopen = mock_error
        hb.tick()
        self.assertEqual(mock_error.call_count, 2)

    def test_retry_max_retries(self):
        hb = self.new_heartbeat_task(gap_secs=1, interval_secs=100, max_retries=2)
        mock_error = Mock(side_effect=URLError(500))
        hb._urllib2.urlopen = mock_error
        hb.tick()
        self.assertEqual(mock_error.call_count, 2)

    def test_retry_time_limit(self):
        hb = self.new_heartbeat_task(gap_secs=1, interval_secs=5, max_retries=10)
        mock_error = Mock(side_effect=URLError(500))
        hb._urllib2.urlopen = mock_error
        hb.tick()
        self.assertEqual(mock_error.call_count, 3)

    def test_retry_and_stop_signal(self):
        def side_effect(*args, **kwargs):
            hb.stop_async()
            raise URLError(500)

        hb = self.new_heartbeat_task(gap_secs=1, interval_secs=100, max_retries=10)
        mock_error = Mock(side_effect=side_effect)
        hb._urllib2.urlopen = mock_error
        hb.tick()
        self.assertEqual(mock_error.call_count, 1)


if __name__ == '__main__':
    unittest.main()
