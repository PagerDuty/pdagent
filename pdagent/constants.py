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


from pdagent import enum


# PDQueue event consumption function return codes.
ConsumeEvent = enum(
    'CONSUMED',
    'BAD_ENTRY',
    'STOP_ALL',
    'BACKOFF_SVCKEY_BAD_ENTRY',
    'BACKOFF_SVCKEY_NOT_CONSUMED',
)

# PDEnqueue warnings.
EnqueueWarnings = enum('UMASK_TOO_RESTRICTIVE')

# PD event integration API V1.
EVENTS_API_BASE_V2 = \
    "https://events.pagerduty.com/v2/enqueue"

# PD event service 
SERVICE_KEY_KEY_V2 = "routing_key"    

# PD event integration API V2.
EVENTS_API_BASE_V1 = "https://events.pagerduty.com/generic/2010-04-15/create_event.json"

# PD event service 
SERVICE_KEY_KEY_V1 = "service_key"

# PD heartbeat end-point.
HEARTBEAT_URI = "https://api.pagerduty.com/agent/2014-03-14/heartbeat"
