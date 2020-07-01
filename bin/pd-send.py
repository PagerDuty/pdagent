# Python script to queue an incident event for delayed send to PagerDuty.
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
    parser.add_argument(
        "-k", "--service-key", dest="service_key", required=True,
        help="Service API Key"
        )
    parser.add_argument(
        "-t", "--event-type", dest="event_type", required=True,
        choices=["trigger", "acknowledge", "resolve"],
        help="Event type"
        )
    parser.add_argument(
        "-d", "--description", dest="description",
        help="Short description of the problem"
        )
    parser.add_argument(
        "-i", "--incident-key", dest="incident_key",
        help="Incident Key"
        )
    parser.add_argument(
        "-c", "--client", dest="client",
        help="Client"
        )
    parser.add_argument(
        "-u", "--client-url", dest="client_url",
        help="Client URL"
        )
    parser.add_argument(
        "-f", "--field", action="append", dest="fields",
        help="Add given KEY=VALUE pair to the event details"
        )
    parser.add_argument(
        "-q", "--quiet", action="store_true", dest="quiet",
        help="Operate quietly (no output)"
        )
    return parser


def parse_fields(fields):
    if fields is None:
        return {}
    return dict(f.split("=", 1) for f in fields)


def main():
    from pdagent.pdagentutil import queue_event
    from pdagent.config import load_agent_config
    from pdagent.constants import EnqueueWarnings

    description = "Queue up a trigger, acknowledge, or resolve event to PagerDuty."
    parser = build_queue_arg_parser(description)
    args = parser.parse_args()
    details = parse_fields(args.fields)

    if args.event_type == "trigger":
        if (not args.description) or (not args.description.strip()):
            parser.error("Event type '%s' requires description" % args.event_type)
    else:
        if not args.incident_key:
            parser.error("Event type '%s' requires incident key" % args.event_type)

    agent_config = load_agent_config()

    enqueuer = agent_config.get_enqueuer()
    incident_key, problems = queue_event(
        enqueuer,
        args.event_type, args.service_key, args.incident_key, args.description,
        args.client, args.client_url, details,
        agent_config.get_agent_id(), "pd-send",
        )
    if not args.quiet:
        for problem in problems:
            if problem == EnqueueWarnings.UMASK_TOO_RESTRICTIVE:
                print(
                    "WARNING: Current umask too restrictive. " +
                    "Using default umask (%03o)." % enqueuer.default_umask
                    )
                print(
                    "(For umask requirements, please refer: %s)" %
                    "https://www.pagerduty.com/docs/guides/agent-install-guide/"
                    )
        print("Event processed. Incident Key:", incident_key)


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
