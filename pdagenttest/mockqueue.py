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

class MockQueue:

    def __init__(
            self,
            event=None,
            status=None,
            aggregated=None,
            throttle_info=None,
            cleanup_age_secs=None
            ):
        self.event = event
        self.status = status
        self.expected_aggregated = aggregated
        self.expected_throttle_info = throttle_info
        self.expected_cleanup_age = cleanup_age_secs
        self.consume_code = None
        self.cleaned_up = False

    def get_status(self, aggregated=False, throttle_info=False):
        if aggregated == self.expected_aggregated and \
                throttle_info == self.expected_throttle_info:
            return self.status
        raise Exception(
                (
                    "Received aggregated=%s and throttle_info=%s; " +
                    "expected aggregated=%s and throttle_info=%s"
                ) %
                (
                    aggregated, throttle_info,
                    self.expected_aggregated, self.expected_throttle_info
                )
            )

    def flush(self, consume_func, stop_check_func):
        self.consume_code = consume_func(self.event, self.event)

    def cleanup(self, before):
        if before == self.expected_cleanup_age:
            self.cleaned_up = True
        else:
            raise Exception(
                "Received cleanup_before=%s, expected=%s" %
                (before, self.expected_cleanup_age)
                )
