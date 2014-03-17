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
sudo find $OUTQUEUE_DIR -type f -exec rm -f {} \;


# modify agent check frequency so we wait for lesser time.
sudo sed -i "s#^\#send_interval_secs.*#send_interval_secs=$SEND_INTERVAL_SECS#" $CONFIG_FILE

# agent must flush out queue when it starts up.
test_startup() {
  $BIN_PD_SEND -k $SVC_KEY -t acknowledge -i test$$_1 -f key=value -f foo=bar

  test $(sudo find $OUTQUEUE_DIR -type f | wc -l) -eq 1
  QUEUED_FILE=$(sudo find $OUTQUEUE_DIR -type f )
  test $(sudo stat -c %a $QUEUED_FILE) = "640"

  $BIN_PD_SEND -k $SVC_KEY -t resolve -i test$$_1 -d "Testing"

  test $(sudo find $OUTQUEUE_DIR -type f -name "pdq_*" | wc -l) -eq 2

  start_agent
  test -n "$(agent_pid)"
  sleep $(($SEND_INTERVAL_SECS / 2))  # enough time for agent to flush the queue.
  test $(sudo find $OUTQUEUE_DIR -type f | wc -l) -eq 2
  test $(sudo find $OUTQUEUE_DIR -type f -name "suc_*" | wc -l) -eq 2
}

# agent must flush out queue when it wakes up.
test_wakeup() {
  test $(sudo find $OUTQUEUE_DIR -type f | wc -l) -eq 2
  $BIN_PD_SEND -k $SVC_KEY -t acknowledge -i test$$_2 -f baz=boo
  $BIN_PD_SEND -k $SVC_KEY -t resolve -i test$$_2 -d "Testing"
  # corrupt the latest enqueued file.
  echo "bad json" \
    | sudo tee $(sudo find $OUTQUEUE_DIR -type f -name "pdq_*" | tail -n1) >/dev/null

  sleep $(($SEND_INTERVAL_SECS * 3 / 2))  # sleep-time + extra-time for processing.
  # there must be one error file in outqueue; everything else must be cleared.
  test $(sudo find $OUTQUEUE_DIR -type f | wc -l) -eq 4
  test $(sudo find $OUTQUEUE_DIR -type f -name "err_*" | wc -l) -eq 1
  test $(sudo find $OUTQUEUE_DIR -type f -name "suc_*" | wc -l) -eq 3
}

test_startup
test_wakeup
