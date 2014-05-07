#
# Checks commands that access local queue.
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

. $(dirname $0)/util.sh

set -e
set -x

# stop agent and clear outqueue if required.
test -z "$(agent_pid)" || stop_agent
sleep $(( $SEND_INTERVAL_SECS / 2 ))
echo "$(agent_pid)"
test -d $OUTQUEUE_DIR

# restart agent
start_agent

flush_queue() {
  # gives us enough time for the queue to flush
  sleep $(($SEND_INTERVAL_SECS * 3))
}

test_good_events() {
  # empty queue
  sudo find $OUTQUEUE_DIR -type f -exec rm -f {} \;

  # set up two test events
  $BIN_PD_NAGIOS -k $SVC_KEY -t PROBLEM -n service -f HOSTNAME=service.test.local \
    -f SERVICEDESC="test service" -f SERVICESTATE=critical

  $BIN_PD_NAGIOS -k $SVC_KEY -t PROBLEM -n host -f HOSTNAME=host.test.local \
    -f HOSTSTATE=critical

  flush_queue

  test $(sudo find $OUTQUEUE_DIR/suc -type f | wc -l) -eq 2

  # resolve the events

  $BIN_PD_NAGIOS -k $SVC_KEY -t RECOVERY -n service -f HOSTNAME=service.test.local \
    -f SERVICEDESC="test service" -f SERVICESTATE=critical

  $BIN_PD_NAGIOS -k $SVC_KEY -t RECOVERY -n host -f HOSTNAME=host.test.local \
    -f HOSTSTATE=critical

  flush_queue

  test $(sudo find $OUTQUEUE_DIR/suc -type f | wc -l) -eq 4
}

test_missing_fields() {
  # testing various commands that should fail
  set +e

  # required fields for 'service' = HOSTNAME< SERVICEDESC, SERVICESTATE

  $BIN_PD_NAGIOS -k testkey -t PROBLEM -n service -f HOSTNAME=service.test.local \
    -f SERVICEDESC="test service"
  test $? -ne 0 || exit 1

  $BIN_PD_NAGIOS -k testkey -t PROBLEM -n service -f HOSTNAME=service.test.local \
    -f SERVICESTATE=critical
  test $? -ne 0 || exit 1

  $BIN_PD_NAGIOS -k testkey -t PROBLEM -n service -f SERVICEDESC="test service" \
    -f SERVICESTATE=critical
  test $? -ne 0 || exit 1

  # required fields for 'hosts' = HOSTNAME, HOSTSTATE

  $BIN_PD_NAGIOS -k testkey -t PROBLEM -n host -f HOSTNAME=host.test.local
  test $? -ne 0 || exit 1

  $BIN_PD_NAGIOS -k testkey -t PROBLEM -n host -f HOSTSTATE=critical
  test $? -ne 0 || exit 1

  set -e
}

test_incident_key() {
  # stop the agent, since we don't really want these things to send
  test -z "$(agent_pid)" || stop_agent

  # service-type
  result=`$BIN_PD_NAGIOS -k $SVC_KEY -t PROBLEM -n service -f HOSTNAME=service.test.local \
    -f SERVICEDESC="test service" -f SERVICESTATE=critical`
  expected="event_source=service;host_name=service.test.local;service_desc=test service"
  test `echo $result | grep -c "$expected"` -eq 1

  # host-type
  result=`$BIN_PD_NAGIOS -k $SVC_KEY -t PROBLEM -n host -f HOSTNAME=host.test.local \
    -f HOSTSTATE=critical`
  expected="event_source=host;host_name=host.test.local"
  test `echo $result | grep -c "$expected"` -eq 1

  # explicit incident key
  result=`$BIN_PD_NAGIOS -k $SVC_KEY -t PROBLEM -n host -f HOSTNAME=host.test.local \
    -f HOSTSTATE=critical -i 1123581321`
  expected="1123581321"
  test `echo $result | grep -c "$expected"` -eq 1

  start_agent
}

# test_bad_notification_type() {
# }

# test_bad_event_type() {
# }

test_incident_key
test_good_events
test_missing_fields