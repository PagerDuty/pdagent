
import json
import unittest

from pdagent.phonehome import PhoneHomeThread


AGENT_ID = "test123"
SYSTEM_INFO = {
    "name": "Test",
    "version": "Infinity"
}
RESPONSE_FREQUENCY_SEC = 30


class MockHttpsCommunicator:

    def __init__(self):
        self.request = None
        self.response = None

    def urlopen(self, request):
        self.request = request
        return self.response


class MockQueue:

    def __init__(self):
        self.status = {
            "foo": "bar"
        }

    def get_status(self, aggregated=False, throttle_info=False):
        if aggregated and throttle_info:
            return self.status
        raise Exception(
            "Received aggregated=%s and throttle_info=%s" %
            (aggregated, throttle_info)
            )


class MockResponse:

    def __init__(self, code=200, data=None):
        self.code = code
        self.data = data

    def getcode(self):
        return self.code

    def read(self):
        return self.data


class PhoneHomeTest(unittest.TestCase):

    def newPhoneHomeThread(self):
        ph = PhoneHomeThread(
            RESPONSE_FREQUENCY_SEC + 10,  # something different from response.
            MockQueue(),
            AGENT_ID,
            SYSTEM_INFO)
        ph._api_communicator = MockHttpsCommunicator()
        return ph

    def test_data(self):
        from pdagent.constants import AGENT_VERSION
        ph = self.newPhoneHomeThread()

        ph.tick()
        self.assertEqual(
            json.loads(ph._api_communicator.request.get_data()),
            {
                "agent_id": AGENT_ID,
                "agent_version": AGENT_VERSION,
                "system_info": SYSTEM_INFO,
                "agent_stats": ph.pd_queue.status
            })

    def test_no_sys_info(self):
        from pdagent.constants import AGENT_VERSION
        ph = self.newPhoneHomeThread()
        ph.system_info = None

        ph.tick()
        self.assertEqual(
            json.loads(ph._api_communicator.request.get_data()),
            {
                "agent_id": AGENT_ID,
                "agent_version": AGENT_VERSION,
                "agent_stats": ph.pd_queue.status
            })

    def test_no_queue_stats(self):
        from pdagent.constants import AGENT_VERSION
        ph = self.newPhoneHomeThread()

        ph.pd_queue.status = None

        ph.tick()
        self.assertEqual(
            json.loads(ph._api_communicator.request.get_data()),
            {
                "agent_id": AGENT_ID,
                "agent_version": AGENT_VERSION,
                "system_info": SYSTEM_INFO,
            })

    def test_new_frequency(self):
        ph = self.newPhoneHomeThread()
        ph._api_communicator.response = MockResponse(
            data=json.dumps({
                "next_checkin_interval_seconds": RESPONSE_FREQUENCY_SEC
                })
            )
        ph.tick()
        self.assertEquals(RESPONSE_FREQUENCY_SEC, ph._sleep_secs)

    def test_communication_error(self):
        ph = self.newPhoneHomeThread()

        def err_func(url, **kwargs):
            raise Exception

        ph._api_communicator.urlopen = err_func
        ph.tick()
        # no errors here means communication errors were handled.

    def test_bad_response_data(self):
        ph = self.newPhoneHomeThread()
        ph._api_communicator.response = MockResponse(data="bad")
        ph.tick()
        # no errors here means bad response data was handled.


if __name__ == '__main__':
    unittest.main()
