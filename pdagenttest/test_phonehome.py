
import json
import unittest

from pdagent.constants import AGENT_VERSION
from pdagent.phonehome import PhoneHomeTask
from pdagenttest.mockqueue import MockQueue
from pdagenttest.mockresponse import MockResponse
from pdagenttest.mockurllib import MockUrlLib


AGENT_ID = "test123"
SYSTEM_INFO = {
    "name": "Test",
    "version": "Infinity"
}
RESPONSE_FREQUENCY_SEC = 30


class PhoneHomeTest(unittest.TestCase):

    def new_phone_home_task(self):
        ph = PhoneHomeTask(
            RESPONSE_FREQUENCY_SEC + 10,  # something different from response.
            self.mock_queue(),
            AGENT_ID,
            SYSTEM_INFO)
        ph._urllib2 = MockUrlLib()
        return ph

    def mock_queue(self):
        return MockQueue(
            status={"foo": "bar"},
            aggregated=True,
            throttle_info=True
            )

    def test_data(self):
        ph = self.new_phone_home_task()
        ph.tick()
        self.assertEqual(
            json.loads(ph._urllib2.request.get_data()),
            {
                "agent_id": AGENT_ID,
                "agent_version": AGENT_VERSION,
                "system_info": SYSTEM_INFO,
                "agent_stats": ph.pd_queue.status
            })

    def test_new_frequency(self):
        ph = self.new_phone_home_task()
        ph._urllib2.response = MockResponse(
            data=json.dumps({
                "next_checkin_interval_seconds": RESPONSE_FREQUENCY_SEC
                })
            )
        ph.tick()
        self.assertEquals(RESPONSE_FREQUENCY_SEC, ph._interval_secs)

    def test_communication_error(self):
        ph = self.new_phone_home_task()
        def err_func(url, **kwargs):
            raise Exception

        ph._urllib2.urlopen = err_func
        ph.tick()
        # no errors here means communication errors were handled.

    def test_bad_response_data(self):
        ph = self.new_phone_home_task()
        ph._urllib2.response = MockResponse(data="bad")
        ph.tick()
        # no errors here means bad response data was handled.


if __name__ == '__main__':
    unittest.main()
