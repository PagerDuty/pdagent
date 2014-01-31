
import json
import unittest
from urllib2 import HTTPError, URLError

from pdagent.constants import ConsumeEvent
from pdagent.sendevent import SendEventThread
from pdagent.thirdparty import httpswithverify
from pdagent.thirdparty.ssl_match_hostname import CertificateError


FREQUENCY_SEC = 30
SEND_TIMEOUT_SEC = 1
CLEANUP_FREQUENCY_SEC = 60
CLEANUP_AGE_SEC = 120

INCIDENT_KEY = "123"


class MockCommunicator:

    def __init__(self):
        self.request = None
        self.response = None

    def urlopen(self, request, **kwargs):
        self.request = request
        return self.response


class MockQueue:

    def __init__(self):
        self.event = json.dumps({
            "event_type":"acknowledge",
            "service_key":"foo",
            "incident_key": INCIDENT_KEY,
            "description":"test",
            "details":{}
            })
        self.consume_code = None
        self.cleaned_up = False

    def flush(self, consume_func):
        self.consume_code = consume_func(self.event)

    def cleanup(self, before):
        if before == CLEANUP_AGE_SEC:
            self.cleaned_up = True
        else:
            raise Exception("Received cleanup_before=%s" % before)

class MockResponse:

    default_data = json.dumps({
        "status": "success",
        "incident_key": INCIDENT_KEY,
        "message": "Event processed"
        })

    def __init__(self, code=200, data=default_data):
        self.code = code
        self.data = data

    def getcode(self):
        return self.code

    def read(self):
        return self.data


class SendEventTest(unittest.TestCase):

    def newSendEventThread(self):
        s = SendEventThread(
            MockQueue(),
            FREQUENCY_SEC,
            SEND_TIMEOUT_SEC,
            CLEANUP_FREQUENCY_SEC,
            CLEANUP_AGE_SEC
        )
        s._api_communicator = MockCommunicator()
        return s

    def test_send_and_cleanup(self):
        s = self.newSendEventThread()
        s._api_communicator.response = MockResponse()

        s.tick()

        self.assertEquals(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        self.assertTrue(s.pd_queue.cleaned_up)

    # --------------------------------------------------------------------------
    # test behaviour for queue-related errors
    # --------------------------------------------------------------------------

    def test_empty_queue(self):
        s = self.newSendEventThread()

        def empty_queue_flush(**args):
            from pdagent.pdqueue import EmptyQueueError
            raise EmptyQueueError

        s.pd_queue.flush = empty_queue_flush

        s.tick()

        self.assertTrue(s.pd_queue.consume_code is None)
        # empty-queue handled, and cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

    def test_queue_errors(self):
        s = self.newSendEventThread()

        def erroneous_queue_flush(**args):
            raise Exception

        s.pd_queue.flush = erroneous_queue_flush

        s.tick()

        self.assertTrue(s.pd_queue.consume_code is None)
        # queue error handled; cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

    def test_no_cleanup(self):
        import time

        s = self.newSendEventThread()
        s._api_communicator.response = MockResponse()
        s.last_cleanup_time = int(time.time()) - 1

        s.tick()

        # queue is flushed normally...
        self.assertEquals(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        # ... and cleanup is not invoked because it is not time for it.
        self.assertFalse(s.pd_queue.cleaned_up)

    def test_cleanup_errors(self):
        s = self.newSendEventThread()
        s._api_communicator.response = MockResponse()

        def erroneous_cleanup(**args):
            raise Exception

        s.pd_queue.cleanup = erroneous_cleanup

        s.tick()

        # queue is flushed normally...
        self.assertEquals(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        # ... and cleanup errors have been handled since we are .

    # --------------------------------------------------------------------------
    # test behaviour for events-API endpoint-related errors.
    # (We'll mostly make do with mocked network connections because test specs
    # for httpswithverify module verify some relevant real response
    # characteristics.)
    # --------------------------------------------------------------------------

    def test_url_connection_error(self):
        s = self.newSendEventThread()

        def error(*args, **kwargs):
            httpswithverify.urlopen("https://localhost/error")

        s._api_communicator.urlopen = error

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
        s = self.newSendEventThread()
        s._api_communicator.response = MockResponse(data="bad")

        s.tick()

        self.assertEquals(s.pd_queue.consume_code, ConsumeEvent.CONSUMED)
        self.assertTrue(s.pd_queue.cleaned_up)

    def _verifyConsumeCodeForError(self, exception, expected_code):
        s = self.newSendEventThread()

        def error(*args, **kwargs):
            raise exception

        s._api_communicator.urlopen = error

        s.tick()
        self.assertEquals(s.pd_queue.consume_code, expected_code)
        # error handled; cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

    def _verifyConsumeCodeForHTTPError(self, error_code, expected_code):
        s = self.newSendEventThread()

        s._api_communicator.response = MockResponse(code=error_code)

        s.tick()
        self.assertEquals(s.pd_queue.consume_code, expected_code)
        # error handled; cleanup is still invoked.
        self.assertTrue(s.pd_queue.cleaned_up)

if __name__ == '__main__':
    unittest.main()
