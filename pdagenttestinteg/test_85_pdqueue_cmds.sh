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

# check that queue status is printed out correctly.
test_status() {
  sudo find $OUTQUEUE_DIR -type f -exec rm -f {} \;

  $BIN_PD_SEND -k key1 -t trigger -i "test11" -d "Test incident 1.1"

  $BIN_PD_SEND -k key2 -t trigger -i "test21" -d "Test incident 2.1"
  $BIN_PD_SEND -k key2 -t acknowledge -i "test21"
  sudo mv $(sudo find $OUTQUEUE_DIR/pdq -type f | sort | tail -n1) \
        $OUTQUEUE_DIR/err

  $BIN_PD_SEND -k key3 -t trigger -i "test31" -d "Test incident 3.1"
  sudo mv $(sudo find $OUTQUEUE_DIR/pdq -type f | sort | tail -n1) \
        $OUTQUEUE_DIR/suc

  stats=$(sudo $BIN_PD_QUEUE status | tail -n+3 | tr -s " " \
        | hexdump -e '"%_c"')
  test "$stats" = 'key1 1 0 0\nkey2 1 0 1\nkey3 0 1 0\n'

  stats=$(sudo $BIN_PD_QUEUE status -k key2 | tail -n+3 | tr -s " " \
        | hexdump -e '"%_c"')
  test "$stats" = 'key2 1 0 1\n'
}

# agent must flush out queue when it wakes up.
test_retry() {
  sudo find $OUTQUEUE_DIR -type f -exec rm -f {} \;

  $BIN_PD_SEND -k key1 -t trigger -i "test11" -d "Test incident 1.1"

  $BIN_PD_SEND -k key2 -t trigger -i "test21" -d "Test incident 2.1"
  $BIN_PD_SEND -k key2 -t acknowledge -i "test21"
  sudo mv $(sudo find $OUTQUEUE_DIR/pdq -type f | sort | tail -n1) \
        $OUTQUEUE_DIR/err

  $BIN_PD_SEND -k key1 -t trigger -i "test12" -d "Test incident 1.2"
  sudo mv $(sudo find $OUTQUEUE_DIR/pdq -type f | sort | tail -n1) \
        $OUTQUEUE_DIR/suc
  $BIN_PD_SEND -k key1 -t trigger -i "test13" -d "Test incident 1.3"
  sudo mv $(sudo find $OUTQUEUE_DIR/pdq -type f | sort | tail -n1) \
        $OUTQUEUE_DIR/err

  $BIN_PD_SEND -k key3 -t trigger -i "test31" -d "Test incident 3.1"
  sudo mv $(sudo find $OUTQUEUE_DIR/pdq -type f | sort | tail -n1) \
        $OUTQUEUE_DIR/err

  test $(sudo find $OUTQUEUE_DIR/pdq -type f | wc -l) -eq 2
  test $(sudo find $OUTQUEUE_DIR/err -type f | wc -l) -eq 3
  test $(sudo find $OUTQUEUE_DIR/suc -type f | wc -l) -eq 1

  # retry events for key2.
  test $(sudo $BIN_PD_QUEUE retry -k key2 | cut -d' ' -f1) -eq 1
  test $(sudo find $OUTQUEUE_DIR/pdq -type f | wc -l) -eq 3
  test $(sudo find $OUTQUEUE_DIR/err -type f | wc -l) -eq 2
  test $(sudo find $OUTQUEUE_DIR/suc -type f | wc -l) -eq 1

  # retry all events.
  test $(sudo $BIN_PD_QUEUE retry -a | cut -d' ' -f1) -eq 2
  test $(sudo find $OUTQUEUE_DIR/pdq -type f | wc -l) -eq 5
  test $(sudo find $OUTQUEUE_DIR/err -type f | wc -l) -eq 0
  test $(sudo find $OUTQUEUE_DIR/suc -type f | wc -l) -eq 1
}

test_status
test_retry
