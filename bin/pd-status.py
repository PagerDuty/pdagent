#!/usr/bin/python
#
# Python script to provide the status of incident events that the agent knows
# of.
#
# Copyright (c) 2013, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#

def build_arg_parser(description):
    from pdagent.argparse import ArgumentParser
    parser = ArgumentParser(description=description)
    parser.add_argument("-k", "--service-key", dest="service_key",
            help="Print status of events in given Service API Key")
    return parser

def main():
    from pdagent.pdagentutil import get_status
    description = "Print out status of events that agent knows of."
    parser = build_arg_parser(description)
    args = parser.parse_args()

    status = get_status(args.service_key)  # 'None' for all-keys.
    if not status:
        print "Nothing to report."
    else:
        fmt = "%-35s%10s%10s"
        print fmt % ("Service Key", "Pending", "In Error")
        print (fmt % ("", "", "")).replace(" ", "=")
        for (svc_key, state) in status.iteritems():
            print fmt % (
                svc_key,
                state.get("pending", 0),
                state.get("error", 0))


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
