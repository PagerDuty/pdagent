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


def main():
    from pdagent.pdagentutil import send_event, build_send_opt_parser, parse_fields
    usage = "Usage: %prog -s <service-key> -i <incident-key> [-d <description>] [-f KEY=VALUE ...]"
    parser = build_send_opt_parser(usage)
    (options, args) = parser.parse_args()
    if len(args):
        parser.error("Incorrect number of arguments")
    if not options.service_key:
        parser.error("Service key is required")

    details = parse_fields(options.fields)
    send_event("acknowledge", options.service_key, options.incident_key, options.description, details)

if __name__ == "__main__":
    import sys
    from os.path import abspath, dirname, join
    proj_dir = dirname(dirname(abspath(__file__)))
    sys.path.append(proj_dir)
    main()

