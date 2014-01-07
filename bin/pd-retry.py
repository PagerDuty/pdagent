#!/usr/bin/python
#
# Python script to resurrect incident events that are considered 'dead' due to
# possible errors earlier.
#
# Copyright (c) 2013, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#

def build_arg_parser(description):
    from pdagent.argparse import ArgumentParser
    parser = ArgumentParser(description=description)
    parser.add_argument("-k", "--service-key", dest="service_key",
            help="Retry events in given Service API Key"),
    parser.add_argument("-a", "--all-keys", action="store_true",
            dest="all_keys", help="Retry events in all Service API Keys")
    return parser

def main():
    from pdagent.pdagentutil import resurrect_events
    agent_config = pdagent.config.load_agent_config()
    description = "Set up 'dead' PagerDuty events for retry."
    parser = build_arg_parser(description)
    args = parser.parse_args()

    # We explicitly require either a specific service key, or an indication that
    # events of all service keys can be resurrected. We don't want to assume
    # anything here.
    if not args.service_key and not args.all_keys:
        parser.error("A specific service key or a flag for all keys required")
    elif args.service_key and args.all_keys:
        parser.error(
            "Only one of specific service key or flag for all keys required")

    queue_config = dict(agent_config.get_main_config())
    queue_config.update(agent_config.get_conf_dirs())
    resurrect_events(queue_config, args.service_key)  # 'None' for all keys.
    print "Events set up for retry."


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
