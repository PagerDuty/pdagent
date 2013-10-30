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


def build_send_arg_parser(description, incident_key_required):
    from pdagent.argparse import ArgumentParser
    parser = ArgumentParser(description=description)
    parser.add_argument("-k", "--service-key", dest="service_key", required=True,
            help="Service API Key")
    parser.add_argument("-i", "--incident-key", dest="incident_key", required=incident_key_required,
            help="Incident Key"),
    parser.add_argument("-d", "--description", dest="description", required=True,
            help="Short description of the problem"),
    parser.add_argument("-f", "--field", action="append", dest="fields",
            help="Add given KEY=VALUE pair to the event details"
            )
    return parser


def parse_fields(fields):
    if fields is None:
        return {}
    return dict(f.split("=", 2) for f in fields)

