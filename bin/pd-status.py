#!/usr/bin/python
#
# Python script to provide the status of incident events that the agent knows
# of.
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
                state.get("succeeded", 0),
                state.get("failed", 0))


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
