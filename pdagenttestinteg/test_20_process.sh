#
# Checks that agent processes events.
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

test "$SVC_KEY" != "CHANGEME" || {
  echo "Please change SVC_KEY in $(dirname $0)/util.sh" >&2
  exit 1
}

# stop agent and clear outqueue if required.
test -z "$(agent_pid)" || stop_agent
test -d $OUTQUEUE_DIR
sudo find $OUTQUEUE_DIR -type f -exec rm -f {} \;
# modify agent check frequency so we wait for lesser time.
sudo sed -i "s#^send_interval_secs.*#send_interval_secs=$SEND_INTERVAL_SECS#" $CONFIG_FILE

# agent must flush out queue when it starts up.
test_startup() {
  i_key="test1"
  $BIN_PD_SEND -k $SVC_KEY -t trigger -i $i_key -d "Test incident 1" -f key1=value1 -f key2=subkey=subvalue -c "PagerDuty" -u "https://www.pagerduty.com"

  test $(sudo find $OUTQUEUE_DIR -type f | wc -l) -eq 1
  queued_file=$(sudo find $OUTQUEUE_DIR -type f )
  test $(sudo stat -c %a $queued_file) = "644"
  tmp_file=/tmp/$(basename $queued_file)
  sudo sed -r 's/"agent_id":"[a-f0-9-]+"/"agent_id":"SOME_ID"/g ;
    s/"queued_at":"[0-9]{4}(-[0-9]{2}){2}T[0-9]{2}(:[0-9]{2}){2}Z"/"queued_at":"SOME_TIME"/g ;
    s/"service_key":"'$SVC_KEY'"/"service_key":"SOME_SERVICE_KEY"/g' \
    $queued_file >$tmp_file
  sudo grep 'agent_id":"SOME_ID' $tmp_file

  $BIN_PD_SEND -k $SVC_KEY -t acknowledge -i $i_key -f key=value -f foo=bar
  $BIN_PD_SEND -k $SVC_KEY -t resolve -i $i_key -d "Testing"

  test $(sudo find $OUTQUEUE_DIR/pdq -type f | wc -l) -eq 3

  start_agent
  test -n "$(agent_pid)"
  sleep $(($SEND_INTERVAL_SECS))  # enough time for agent to flush the queue.
  test $(sudo find $OUTQUEUE_DIR/pdq -type f | wc -l) -eq 0
  test $(sudo find $OUTQUEUE_DIR/suc -type f | wc -l) -eq 3
}

# agent must flush out queue when it wakes up.
test_wakeup() {
  test $(sudo find $OUTQUEUE_DIR -type f | wc -l) -eq 3

  i_key="test$$_2"
  $BIN_PD_SEND -k $SVC_KEY -t trigger -i $i_key -d "Test incident 2"
  $BIN_PD_SEND -k $SVC_KEY -t acknowledge -i $i_key -f baz=boo
  # corrupt the ack-event file.
  echo "bad json" \
    | sudo tee $(sudo find $OUTQUEUE_DIR/pdq -type f | tail -n1) >/dev/null
  $BIN_PD_SEND -k $SVC_KEY -t resolve -i $i_key -d "Testing"

  sleep $(($SEND_INTERVAL_SECS * 3))  # sleep-time + extra-time for processing.
  # there must be one error file in outqueue; everything else must be cleared.
  test $(sudo find $OUTQUEUE_DIR/pdq -type f | wc -l) -eq 0
  test $(sudo find $OUTQUEUE_DIR/err -type f | wc -l) -eq 1
  test $(sudo find $OUTQUEUE_DIR/suc -type f | wc -l) -eq 5
}

test_startup
test_wakeup
