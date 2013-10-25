#!/usr/bin/env python
#
# Python script to acknowledge an incident in PagerDuty.
#
# Copyright (c) 2013, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#
# Uses the PagerDuty Integration API:
# http://developer.pagerduty.com/documentation/integration/events
#

from pdagentutil import integration_api_post, build_send_opt_parser, parse_fields


def acknowledge_event(service_key, incident_key, description, details):
    d = {
        "service_key": service_key,
        "event_type": "acknowledge",
        "incident_key": incident_key,
        "details": details,
    }
    if description is not None:
        d["description"] = description

    print "Acknowledging incident..."
    http_code, result = integration_api_post(d)
    print "HTTP status code:", http_code
    print "Response data:", repr(result)
    if result["status"] == "success":
        incident_key = result["incident_key"]
        print "Success! incident_key =", incident_key
    else:
        print "Error! Reason:", str(response)

def main():
    usage = "Usage: %prog -s <service-key> -i <incident-key> [-d <description>] [-f KEY=VALUE ...]"
    parser = build_send_opt_parser(usage)
    (options, args) = parser.parse_args()
    if len(args):
        parser.error("Incorrect number of arguments")
    if not options.service_key:
        parser.error("Service key is required")

    details = parse_fields(options.fields)
    acknowledge_event(options.service_key, options.incident_key, options.description, details)

if __name__ == "__main__":
    main()

