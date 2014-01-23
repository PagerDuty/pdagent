#!/usr/bin/python
#
# Python script to queue an incident event for delayed send to PagerDuty.
#
# Copyright (c) 2013, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#

def build_queue_arg_parser(description):
    from pdagent.thirdparty.argparse import ArgumentParser
    parser = ArgumentParser(description=description)
    parser.add_argument("-k", "--service-key", dest="service_key", required=True,
            help="Service API Key")
    parser.add_argument("-t", "--event-type", dest="event_type", required=True,
            choices=["trigger", "acknowledge", "resolve"],
            help="Event type")
    parser.add_argument("-d", "--description", dest="description",
            help="Short description of the problem"),
    parser.add_argument("-i", "--incident-key", dest="incident_key",
            help="Incident Key"),
    parser.add_argument("-f", "--field", action="append", dest="fields",
            help="Add given KEY=VALUE pair to the event details"
            )
    return parser

def parse_fields(fields):
    if fields is None:
        return {}
    return dict(f.split("=", 2) for f in fields)

def main():
    from pdagent.pdagentutil import queue_event
    from pdagent.config import load_agent_config

    description = "Queue up a trigger, acknowledge or resolve event to PagerDuty."
    parser = build_queue_arg_parser(description)
    args = parser.parse_args()
    details = parse_fields(args.fields)

    if args.event_type == "trigger":
        if not args.description:
            parser.error("Event type '%s' requires description" % args.event_type)
    else:
        if not args.incident_key:
            parser.error("Event type '%s' requires incident key" % args.event_type)

    queue_event(
        load_agent_config().get_queue(),
        args.event_type, args.service_key, args.incident_key, args.description,
        details
        )
    print "Event processed."


if __name__ == "__main__":
    try:
        import pdagent.config
    except ImportError:
        # Fix up for dev layout
        import sys
        from os.path import realpath, dirname
        sys.path.append(dirname(dirname(realpath(__file__))))
        import pdagent.config
    main()
