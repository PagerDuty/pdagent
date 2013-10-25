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

from pdagentutil import send_event, build_send_opt_parser, parse_fields

def main():
    usage = "Usage: %prog -s <service-key> [-i <incident-key>] -d <description> [-f KEY=VALUE ...]"
    parser = build_send_opt_parser(usage)
    (options, args) = parser.parse_args()
    if len(args):
        parser.error("Incorrect number of arguments")
    if not options.service_key:
        parser.error("Service key is required")
    if not options.description:
        parser.error("Problem description is required")

    details = parse_fields(options.fields)
    send_event("trigger", options.service_key, options.incident_key, options.description, details)

if __name__ == "__main__":
    main()

