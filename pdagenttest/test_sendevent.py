
import json
import unittest
from urllib2 import URLError

from pdagent.constants import ConsumeEvent
from pdagent.sendevent import SendEventThread
from pdagent.thirdparty import httpswithverify
from pdagent.thirdparty.ssl_match_hostname import CertificateError
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
    "details": {}
    })


class SendEventTest(unittest.TestCase):

    def new_send_event_thread(self):
        s = SendEventThread(
            self.mock_queue(),
            FREQUENCY_SEC,
            SEND_TIMEOUT_SEC,
            CLEANUP_FREQUENCY_SEC,
            CLEANUP_AGE_SEC
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

    def test_send_and_cleanup(self):
        s = self.new_send_event_thread()
        s._urllib2.response = self.mock_response()
        s.tick()
        self.assertEquals(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        self.assertTrue(s.pd_queue.cleaned_up)

    # --------------------------------------------------------------------------
    # test behaviour for queue-related errors
    # --------------------------------------------------------------------------

    def test_empty_queue(self):
        def empty_queue_flush(**args):
            from pdagent.pdqueue import EmptyQueueError
            raise EmptyQueueError

        s = self.new_send_event_thread()
        s.pd_queue.flush = empty_queue_flush
        s.tick()
        self.assertTrue(s.pd_queue.consume_code is None)
        # empty-queue handled, and cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

    def test_queue_errors(self):
        def erroneous_queue_flush(**args):
            raise Exception

        s = self.new_send_event_thread()
        s.pd_queue.flush = erroneous_queue_flush
        s.tick()
        self.assertTrue(s.pd_queue.consume_code is None)
        # queue error handled; cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

    def test_no_cleanup(self):
        import time

        s = self.new_send_event_thread()
        s._urllib2.response = self.mock_response()
        s.last_cleanup_time = int(time.time()) - 1
        s.tick()
        # queue is flushed normally...
        self.assertEquals(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        # ... and cleanup is not invoked because it is not time for it.
        self.assertFalse(s.pd_queue.cleaned_up)

    def test_cleanup_errors(self):
        def erroneous_cleanup(**args):
            raise Exception

        s = self.new_send_event_thread()
        s._urllib2.response = self.mock_response()
        s.pd_queue.cleanup = erroneous_cleanup
        s.tick()
        # queue is flushed normally...
        self.assertEquals(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        # ... and cleanup errors have been handled.

    # --------------------------------------------------------------------------
    # test behaviour for events-API endpoint-related errors.
    # (We'll mostly make do with mocked network connections because test specs
    # for httpswithverify module verify some relevant real response
    # characteristics.)
    # --------------------------------------------------------------------------

    def test_url_connection_error(self):
        def error(*args, **kwargs):
            httpswithverify.urlopen("https://localhost/error")

        s = self.new_send_event_thread()
        s._urllib2.urlopen = error
        s.tick()
        self.assertEquals(s.pd_queue.consume_code, ConsumeEvent.NOT_CONSUMED)
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
            ConsumeEvent.NOT_CONSUMED
            )

    def test_generic_error(self):
        self._verifyConsumeCodeForError(Exception(), ConsumeEvent.NOT_CONSUMED)

    def test_3xx(self):
        self._verifyConsumeCodeForHTTPError(300, ConsumeEvent.NOT_CONSUMED)
        self._verifyConsumeCodeForHTTPError(399, ConsumeEvent.NOT_CONSUMED)

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
        s = self.new_send_event_thread()
        s._urllib2.response = self.mock_response(data="bad")
        s.tick()
        self.assertEquals(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        self.assertTrue(s.pd_queue.cleaned_up)

    def _verifyConsumeCodeForError(self, exception, expected_code):
        def error(*args, **kwargs):
            raise exception

        s = self.new_send_event_thread()
        s._urllib2.urlopen = error
        s.tick()
        self.assertEquals(s.pd_queue.consume_code, expected_code)
        # error handled; cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

    def _verifyConsumeCodeForHTTPError(self, error_code, expected_code):
        s = self.new_send_event_thread()
        s._urllib2.response = self.mock_response(code=error_code)
        s.tick()
        self.assertEquals(s.pd_queue.consume_code, expected_code)
        # error handled; cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

if __name__ == '__main__':
    unittest.main()
