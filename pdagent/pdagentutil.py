#
# Python utility module for sending events to PagerDuty Integration API.
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

def send_event(event_type, service_key, incident_key, description, details):
    d = {
        "service_key": service_key,
        "event_type": event_type,
        "incident_key": incident_key,
        "details": details,
    }
    if description is not None:
        d["description"] = description

    print "Sending %s..." % event_type

    j = json.dumps(d)

    request = urllib2.Request(EVENTS_API_BASE)
    request.add_header("Content-type", "application/json")
    request.add_data(j)

    response = urllib2.urlopen(request)
    http_code = response.getcode()
    result = json.loads(response.read())

    print "HTTP status code:", http_code
    print "Response data:", repr(result)
    if result["status"] == "success":
        incident_key = result["incident_key"]
        print "Success! incident_key =", incident_key
    else:
        print "Error! Reason:", str(response)

