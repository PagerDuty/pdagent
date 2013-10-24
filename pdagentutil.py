#
# Python script to trigger an incident in PagerDuty.
#
# Copyright (c) 2013, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#
# Uses the PagerDuty Integration API:
# http://developer.pagerduty.com/documentation/integration/events
#

import json
import urllib2

EVENTS_API_BASE = "https://events.pagerduty.com/generic/2010-04-15/create_event.json"

def integration_api_post(data):
    j = json.dumps(data)
    
    request = urllib2.Request(EVENTS_API_BASE)
    request.add_header("Content-type", "application/json")
    request.add_data(j)

    response = urllib2.urlopen(request)

    http_code = response.getcode()
    result = json.loads(response.read())

    return http_code, result


def build_send_opt_parser(usage):
    from optparse import OptionParser, make_option
    option_list = [
        make_option("-s", "--service-key", dest="service_key", help="Service API Key"),
        make_option("-i", "--incident-key", dest="incident_key", help="Incident Key"),
        make_option("-d", "--description", dest="description", help="Short description of the problem"),
        ]
    return OptionParser(usage, option_list)

