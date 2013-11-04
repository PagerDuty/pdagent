#!/usr/bin/env python
#
# Python script to queue up an acknowledge for an incident in PagerDuty.
#
# Copyright (c) 2013, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#
# Uses the PagerDuty Integration API:
# http://developer.pagerduty.com/documentation/integration/events
#


def main():
    from pdagent.pdagentutil import queue_event, build_queue_opt_parser, parse_fields
    usage = "Usage: %prog -s <service-key> -i <incident-key> [-d <description>] [-f KEY=VALUE ...]"
    parser = build_queue_opt_parser(usage)
    (options, args) = parser.parse_args()
    if len(args):
        parser.error("Incorrect number of arguments")
    if not options.service_key:
        parser.error("Service key is required")
    if not options.incident_key:
        parser.error("Incident key is required")

    details = parse_fields(options.fields)
    queue_event("acknowledge", options.service_key, options.incident_key, options.description, details)

if __name__ == "__main__":
    import sys
    from os.path import abspath, dirname, join
    proj_dir = dirname(dirname(abspath(__file__)))
    sys.path.append(proj_dir)
    main()

