#!/usr/bin/env python
#
# Python script to trigger an incident in PagerDuty.
# 
# Copyright (c) 2013, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#
# Uses the PagerDuty Integration API:
# http://developer.pagerduty.com/documentation/integration/events
#

from pdagentutil import integration_api_post


def trigger_event(service_key, incident_key, description):
    d = {
        "service_key": service_key,
        "event_type": "trigger",
        "description": description
    }
    if incident_key:
        d["incident_key"] = incident_key

    print "Triggering incident..."
    http_code, result = integration_api_post(d)
    print "HTTP status code:", http_code
    print "Response data:", repr(result)
    if result["status"] == "success":
        incident_key = result["incident_key"]
        print "Success! incident_key =", incident_key
    else:
        print "Error! Reason:", str(response)


def build_opt_parser():
    from optparse import OptionParser, make_option
    usage = "Usage: %prog -s <service-key> [-i <incident-key>] -d <description> [-f KEY=VALUE ...]"
    option_list = [
        make_option("-s", "--service-key", dest="service_key", help="Service API Key"),
        make_option("-i", "--incident-key", dest="incident_key", help="Incident Key"),
        make_option("-d", "--description", dest="description", help="Short description of the problem"),
        ]
    return OptionParser(usage, option_list)

def main():
    parser = build_opt_parser()
    (options, args) = parser.parse_args()
    if len(args):
        parser.error("Incorrect number of arguments")
    if not options.service_key:
        parser.error("Service key is required")
    if not options.description:
        parser.error("Problem description is required")

    trigger_event(options.service_key, options.incident_key, options.description)

if __name__ == "__main__":
    main()

