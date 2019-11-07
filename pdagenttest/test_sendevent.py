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
from ssl import CertificateError
from six.moves.urllib.error import URLError

from pdagent.constants import ConsumeEvent
from pdagent.sendevent import SendEventTask
from pdagent import http
from pdagenttest.mockqueue import MockQueue
from pdagenttest.mockresponse import MockResponse
from pdagenttest.mockurllib import MockUrlLib

FREQUENCY_SEC = 30
SEND_TIMEOUT_SEC = 1
CLEANUP_FREQUENCY_SEC = 60
CLEANUP_AGE_SEC = 120
INCIDENT_KEY = "123"
DEFAULT_RESPONSE_DATA = json.dumps({
    "status": "success",
    "incident_key": INCIDENT_KEY,
    "message": "Event processed"
    })
SAMPLE_EVENT = json.dumps({
    "event_type": "acknowledge",
    "service_key": "foo",
    "incident_key": INCIDENT_KEY,
    "description": "test",
    "client": "PagerDuty",
    "client_url": "http://www.pagerduty.com",
    "details": {}
    })


class SendEventTest(unittest.TestCase):

    def new_send_event_task(self, source_address='0.0.0.0'):
        s = SendEventTask(
            self.mock_queue(),
            FREQUENCY_SEC,
            CLEANUP_FREQUENCY_SEC,
            CLEANUP_AGE_SEC,
            source_address
        )
        s._urllib2 = MockUrlLib()
        return s

    def mock_queue(self):
        return MockQueue(
            event=SAMPLE_EVENT,
            cleanup_age_secs=CLEANUP_AGE_SEC
            )

    def mock_response(self, code=200, data=DEFAULT_RESPONSE_DATA):
        return MockResponse(code, data)

    def test_source_address_send_and_cleanup(self):
        s = self.new_send_event_task('127.0.0.1')
        s._urllib2.response = self.mock_response()
        s.tick()
        self.assertEqual(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        self.assertTrue(s.pd_queue.cleaned_up)

    def test_send_and_cleanup(self):
        s = self.new_send_event_task()
        s._urllib2.response = self.mock_response()
        s.tick()
        self.assertEqual(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        self.assertTrue(s.pd_queue.cleaned_up)

    # --------------------------------------------------------------------------
    # test behaviour for queue-related errors
    # --------------------------------------------------------------------------

    def test_empty_queue(self):
        def empty_queue_flush(*args, **kwargs):
            from pdagent.pdqueue import EmptyQueueError
            raise EmptyQueueError

        s = self.new_send_event_task()
        s.pd_queue.flush = empty_queue_flush
        s.tick()
        self.assertTrue(s.pd_queue.consume_code is None)
        # empty-queue handled, and cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

    def test_queue_errors(self):
        def erroneous_queue_flush(*args, **kwargs):
            raise Exception

        s = self.new_send_event_task()
        s.pd_queue.flush = erroneous_queue_flush
        s.tick()
        self.assertTrue(s.pd_queue.consume_code is None)
        # queue error handled; cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

    def test_no_cleanup(self):
        import time

        s = self.new_send_event_task()
        s._urllib2.response = self.mock_response()
        s.last_cleanup_time = int(time.time()) - 1
        s.tick()
        # queue is flushed normally...
        self.assertEqual(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        # ... and cleanup is not invoked because it is not time for it.
        self.assertFalse(s.pd_queue.cleaned_up)

    def test_cleanup_errors(self):
        def erroneous_cleanup(*args, **kwargs):
            raise Exception

        s = self.new_send_event_task()
        s._urllib2.response = self.mock_response()
        s.pd_queue.cleanup = erroneous_cleanup
        s.tick()
        # queue is flushed normally...
        self.assertEqual(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        # ... and cleanup errors have been handled.

    # --------------------------------------------------------------------------
    # test behaviour for events-API endpoint-related errors.
    # (We'll mostly make do with mocked network connections because test specs
    # for httpswithverify module verify some relevant real response
    # characteristics.)
    # --------------------------------------------------------------------------

    def test_url_connection_error(self):
        def error(*args, **kwargs):
            http.urlopen("https://localhost/error")

        s = self.new_send_event_task()
        s._urllib2.urlopen = error
        s.tick()
        self.assertEqual(
            s.pd_queue.consume_code,
            ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED
            )
        # error handled; cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

    def test_certificate_error(self):
        self._verifyConsumeCodeForError(CertificateError(), ConsumeEvent.STOP_ALL)

    def test_url_timeout_error(self):
        from socket import timeout
        self._verifyConsumeCodeForError(
            URLError(reason=timeout()),
            ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY
            )

    def test_generic_url_error(self):
        self._verifyConsumeCodeForError(
            URLError(reason=None),
            ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED
            )

    def test_generic_error(self):
        self._verifyConsumeCodeForError(
            Exception(),
            ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED
            )

    def test_3xx(self):
        self._verifyConsumeCodeForHTTPError(
            300,
            ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED
            )
        self._verifyConsumeCodeForHTTPError(
            399,
            ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED
            )

    def test_403(self):
        self._verifyConsumeCodeForHTTPError(
            403,
            ConsumeEvent.BACKOFF_SVCKEY_NOT_CONSUMED
            )

    def test_other_4xx(self):
        self._verifyConsumeCodeForHTTPError(400, ConsumeEvent.BAD_ENTRY)
        self._verifyConsumeCodeForHTTPError(499, ConsumeEvent.BAD_ENTRY)

    def test_5xx(self):
        self._verifyConsumeCodeForHTTPError(
            500,
            ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY
            )
        self._verifyConsumeCodeForHTTPError(
            599,
            ConsumeEvent.BACKOFF_SVCKEY_BAD_ENTRY
            )

    def test_bad_response(self):
        # bad response should not matter for our processing.
        s = self.new_send_event_task()
        s._urllib2.response = self.mock_response(data="bad")
        s.tick()
        self.assertEqual(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        self.assertTrue(s.pd_queue.cleaned_up)

    def _verifyConsumeCodeForError(self, exception, expected_code):
        def error(*args, **kwargs):
            raise exception

        s = self.new_send_event_task()
        s._urllib2.urlopen = error
        s.tick()
        self.assertEqual(s.pd_queue.consume_code, expected_code)
        # error handled; cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

    def _verifyConsumeCodeForHTTPError(self, error_code, expected_code):
        s = self.new_send_event_task()
        s._urllib2.response = self.mock_response(code=error_code)
        s.tick()
        self.assertEqual(s.pd_queue.consume_code, expected_code)
        # error handled; cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

if __name__ == '__main__':
    unittest.main()
