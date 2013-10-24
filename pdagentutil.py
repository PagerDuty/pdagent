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

