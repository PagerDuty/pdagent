#!/usr/bin/env python
#
# Python script to resolve an incident in PagerDuty.
#
# Copyright (c) 2013, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#
# Uses the PagerDuty Integration API:
# http://developer.pagerduty.com/documentation/integration/events
#


def main():
    from pdagent.pdagentutil import send_event, build_send_arg_parser, parse_fields
    description="Send a resolve event to PagerDuty."
    parser = build_send_arg_parser(description, True)
    args = parser.parse_args()
    details = parse_fields(args.fields)
    send_event("resolve", args.service_key, args.incident_key, args.description, details)

if __name__ == "__main__":
    import sys
    from os.path import abspath, dirname, join
    proj_dir = dirname(dirname(abspath(__file__)))
    sys.path.append(proj_dir)
    main()

