# Python script to work on the local queue maintained by PagerDuty Agent.
#
# Copyright (c) 2013-2014, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the copyright holder nor the
#     names of its contributors may be used to endorse or promote products
#     derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#


def build_queue_arg_parser(description):
    from pdagent.thirdparty.argparse import ArgumentParser

    parser = ArgumentParser(description=description)
    subparsers = parser.add_subparsers(title="sub-commands")
    retry_parser_desc = "set up 'dead' PagerDuty events for retry."
    status_parser_desc = "print out status of local event queue."

    retry_parser = subparsers.add_parser(
        "retry",
        description=retry_parser_desc.capitalize(),  # printed as title
        help=retry_parser_desc  # printed in 'options' part of main cmd
    )
    retry_parser.add_argument(
        "-k", "--service-key", dest="service_key",
        help="retry events in given Service API Key (not to be used with -a)"
    )
    retry_parser.add_argument(
        "-a", "--all-keys", action="store_true",
        dest="all_keys",
        help="retry events in all Service API Keys (not to be used with -k)"
    )
    retry_parser.set_defaults(func=_retry)

    status_parser = subparsers.add_parser(
        "status",
        description=status_parser_desc.capitalize(),  # printed as title
        help=status_parser_desc  # printed in 'options' part of main cmd
    )
    status_parser.add_argument(
        "-k", "--service-key", dest="service_key",
        help="print status of events in given Service API Key"
    )
    status_parser.set_defaults(func=_status)

    return parser


def _retry(agent_config, parser, args):
    from pdagent.pdagentutil import resurrect_events

    # We explicitly require either a specific service key, or an indication that
    # events of all service keys can be resurrected. We don't want to assume
    # anything here.
    if not args.service_key and not args.all_keys:
        parser.error("A specific service key or a flag for all keys required")
    elif args.service_key and args.all_keys:
        parser.error(
            "Only one of specific service key or flag for all keys required")
    else:
        count = resurrect_events(
            agent_config.get_queue(),
            args.service_key  # 'None' for all keys.
        )
        print("%d event(s) set up for retry." % count)


def _status(agent_config, _, args):
    # prints queue snapshot stats in this format:
    # Service Key                           Pending   Success  In Error
    # =================================================================
    # key1                                        1         0         0
    # key2                                        1         0         1

    from pdagent.thirdparty.six import iteritems
    from pdagent.thirdparty.six.moves import zip_longest
    from pdagent.pdagentutil import get_stats

    status = get_stats(
        agent_config.get_queue(),
        service_key=args.service_key  # 'None' for all-keys.
    )

    snapshot = status.get("snapshot")
    if not snapshot:
        print("Nothing to report.")
    else:
        # left-aligned service key, right-aligned counts.
        flags = ["-", "", "", ""]
        widths = [35, 10, 10, 10]
        types = ["s", "s", "s", "s"]
        column_fmts = [
            "%" + "".join(e)
            for e in zip_longest(flags, map(str, widths), types)
        ]
        fmt = "".join(column_fmts)
        print(fmt % ("Service Key", "Pending", "Success", "In Error"))
        print("=" * sum(widths))
        empty_dict = dict()
        for (svc_key, state) in sorted(iteritems(snapshot)):
            print(fmt % (
                svc_key,
                state.get("pending_events", empty_dict).get("count", 0),
                state.get("succeeded_events", empty_dict).get("count", 0),
                state.get("failed_events", empty_dict).get("count", 0)
            ))


def main():
    from pdagent.config import load_agent_config

    description = "Access local queue of PagerDuty Agent."
    parser = build_queue_arg_parser(description)
    args = parser.parse_args()
    args.func(load_agent_config(), parser, args)


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
