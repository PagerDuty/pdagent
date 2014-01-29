#!/usr/bin/python
#
# Python script to provide the status of incident events that the agent knows
# of.
#
# Copyright (c) 2013, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#

def build_arg_parser(description):
    from pdagent.thirdparty.argparse import ArgumentParser
    parser = ArgumentParser(description=description)
    parser.add_argument("-k", "--service-key", dest="service_key",
            help="Print status of events in given Service API Key")
    return parser

def main():
    from pdagent.pdagentutil import get_status
    from pdagent.config import load_agent_config

    description = "Print out status of events that agent knows of."
    parser = build_arg_parser(description)
    args = parser.parse_args()

    status = get_status(
        load_agent_config().get_queue(),
        args.service_key)  # 'None' for all-keys.
    if not status.get("service_keys"):
        print "Nothing to report."
    else:
        fmt = "%-35s%10s%10s%10s"
        print fmt % ("Service Key", "Pending", "Success", "In Error")
        print (fmt % ("", "", "", "")).replace(" ", "=")
        for (svc_key, state) in status.get("events", {}).iteritems():
            print fmt % (
                svc_key,
                state.get("pending", 0),
                state.get("success", 0),
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
