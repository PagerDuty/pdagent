#
# Checks charset encoding.
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

# stop agent
test -z "$(agent_pid)" || stop_agent

# utf8 command line must enqueue correctly
test_utf8_trigger() {

  # clear outqueue
  test -d $OUTQUEUE_DIR
  sudo find $OUTQUEUE_DIR -type f -exec rm -f {} \;

  /bin/bash -c "$BIN_PD_SEND -k DUMMY_SERVICE_KEY -t acknowledge -i server.fire -d $'\xC3\xA9'"

  test $(sudo find $OUTQUEUE_DIR -type f | wc -l) -eq 1

  sudo find $OUTQUEUE_DIR/pdq -type f \
    | xargs sudo sed -i -r 's/"agent_id":"[a-f0-9-]+"/"agent_id":"SOME_ID"/g'
  sudo find $OUTQUEUE_DIR/pdq -type f \
    | xargs sudo sed -i -r 's/"queued_at":"[0-9]{4}(-[0-9]{2}){2}T[0-9]{2}(:[0-9]{2}){2}Z"/"queued_at":"SOME_TIME"/g'

  sudo diff \
    $(dirname $0)/test_30_encoding.pdq1.txt \
    $(sudo find $OUTQUEUE_DIR/pdq -type f | tail -n1)

}


test_utf8_trigger
echo "Test $0 successful"
