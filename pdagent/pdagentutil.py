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
    print "Sending %s..." % event_type

    j = _build_event_json_str(event_type, service_key, incident_key, description, details)
    send_event_json_str(j)

def send_event_json_str(event_str):
    request = urllib2.Request(EVENTS_API_BASE)
    request.add_header("Content-type", "application/json")
    request.add_data(event_str)

    response = urllib2.urlopen(request)
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
    print "Queuing %s..." % event_type

    event = _build_event_json_str(event_type, service_key, incident_key, description, details)
    PDQueue().enqueue(event)


def build_queue_opt_parser(usage):
  # for now, queueing options are the same as sending options
  return build_send_opt_parser(usage)

def build_send_opt_parser(usage):
    from optparse import OptionParser, make_option
    option_list = [
        make_option("-s", "--service-key", dest="service_key", help="Service API Key"),
        make_option("-i", "--incident-key", dest="incident_key", help="Incident Key"),
        make_option("-d", "--description", dest="description", help="Short description of the problem"),
        make_option("-f", "--field", action="append", dest="fields",
            help="Add given KEY=VALUE pair to the event details"
            ),
        ]
    return OptionParser(usage, option_list)

def parse_fields(fields):
    return dict(f.split("=", 2) for f in fields)

def _build_event_json_str(event_type, service_key, incident_key, description, details):
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
