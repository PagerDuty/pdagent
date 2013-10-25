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

