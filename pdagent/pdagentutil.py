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

EVENTS_API_BASE = \
    "https://events.pagerduty.com/generic/2010-04-15/create_event.json"


def find_in_sys_path(file_path):
    import os
    import sys
    for directory in sys.path:
        abs_path = os.path.join(directory, file_path)
        if os.access(abs_path, os.R_OK):
            return abs_path
    return None


# TODO move this to agent daemon
def send_event_json_str(event_str):
    from pdagent import httpswithverify
    request = urllib2.Request(EVENTS_API_BASE)
    request.add_header("Content-type", "application/json")
    request.add_data(event_str)

    response = httpswithverify.urlopen(request)
    http_code = response.getcode()
    result = json.loads(response.read())

    print "HTTP status code:", http_code
    print "Response data:", repr(result)
    incident_key = None
    if result["status"] == "success":
        incident_key = result["incident_key"]
        print "Success! incident_key =", incident_key
    else:
        print "Error! Reason:", str(response)
    return (incident_key, http_code)


def queue_event(event_type, service_key, incident_key, description, details):
    from pdqueue import PDQueue

    event = _build_event_json_str(
        event_type, service_key, incident_key, description, details
        )
    PDQueue().enqueue(event)


def _build_event_json_str(
    event_type, service_key, incident_key, description, details
    ):
    d = {
        "service_key": service_key,
        "event_type": event_type,
        "details": details,
    }
    if incident_key is not None:
        d["incident_key"] = incident_key
    if description is not None:
        d["description"] = description

    return json.dumps(d)
