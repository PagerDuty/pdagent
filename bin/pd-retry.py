#!/usr/bin/python
#
# Python script to resurrect incident events that are considered 'dead' due to
# possible errors earlier.
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

def build_arg_parser(description):
    from pdagent.thirdparty.argparse import ArgumentParser
    parser = ArgumentParser(description=description)
    parser.add_argument("-k", "--service-key", dest="service_key",
            help="Retry events in given Service API Key"),
    parser.add_argument("-a", "--all-keys", action="store_true",
            dest="all_keys", help="Retry events in all Service API Keys")
    return parser

def main():
    from pdagent.pdagentutil import resurrect_events
    from pdagent.config import load_agent_config

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

    resurrect_events(
        load_agent_config().get_queue(),
        args.service_key)  # 'None' for all keys.
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
