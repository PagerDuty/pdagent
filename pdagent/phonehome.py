
import json
import logging
import urllib2

from pdagent.constants import AGENT_VERSION, PHONE_HOME_URI
from pdagent.pdthread import RepeatingThread
from pdagent.thirdparty import httpswithverify


logger = logging.getLogger(__name__)


class PhoneHomeThread(RepeatingThread):

    def __init__(
            self,
            heartbeat_frequency_sec,
            pd_queue,
            agent_id,
            system_info
            ):
        RepeatingThread.__init__(self, heartbeat_frequency_sec, True)
        self.pd_queue = pd_queue
        self.agent_id = agent_id
        self.system_info = system_info
        self._urllib2 = httpswithverify  # to ease unit testing.

    def tick(self):
        logger.info("Phoning home")
        try:
            phone_home_json = {
                "agent_id": self.agent_id,
                "agent_version": AGENT_VERSION,
            }
            agent_stats = self.pd_queue.get_status(
                throttle_info=True, aggregated=True
                )
            if agent_stats:
                phone_home_json["agent_stats"] = agent_stats
            if self.system_info:
                phone_home_json["system_info"] = self.system_info

            request = urllib2.Request(PHONE_HOME_URI)
            request.add_header("Content-type", "application/json")
            phone_home_data = json.dumps(phone_home_json)
            request.add_data(phone_home_data)

            logger.debug("Phone-home stats: %s" % phone_home_data)
            try:
                response = self._urllib2.urlopen(request)
                result_str = response.read()
            except:
                logger.error("Error while phoning home:", exc_info=True)
                result_str = None

            if result_str:
                try:
                    result = json.loads(result_str)
                except:
                    logger.warning(
                        "Error reading phone-home response data:",
                        exc_info=True
                        )
                    result = {}

                new_heartbeat_freq = result.get("next_checkin_interval_seconds")
                if new_heartbeat_freq:
                    self.set_delay_secs(new_heartbeat_freq)

        except:
            logger.error("Error while phoning home:", exc_info=True)
