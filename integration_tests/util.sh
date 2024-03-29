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

AGENT_USER=pdagent
BIN_PD_QUEUE=pd-queue
BIN_PD_SEND=pd-send
CONFIG_FILE=/etc/pdagent.conf
PID_FILE=/var/run/pdagent/pdagentd.pid
LOG_FILE=/var/log/pdagent/pdagentd.log
DATA_DIR=/var/lib/pdagent
OUTQUEUE_DIR=$DATA_DIR/outqueue
AGENT_SVC_NAME=pdagent
SEND_INTERVAL_SECS=5
# The service key to use for testing commands like pd-send etc.
SVC_KEY=CHANGEME
export SVC_KEY

# return OS type of current system.
os_type() {
  if [ -e /etc/debian_version ]; then
    echo "debian"
  elif [ -e /etc/redhat-release ]; then
    echo "redhat"
  fi
}

# return pid if agent is running, or empty string if not running.
agent_pid() {
    ps aux | grep ${DOCKER_WORKDIR}/bin/pdagentd | grep -v grep | awk '{print $2}'
}

# start agent if not running.
start_agent() {
    if [ -z "$(agent_pid)" ]; then
        if which systemctl >/dev/null; then
            sudo systemctl start $AGENT_SVC_NAME
        else
            sudo service $AGENT_SVC_NAME start
        fi
    else
        return 0
    fi
}

# stop agent if running.
stop_agent() {
    if [ -n "$(agent_pid)" ]; then
            if which systemctl >/dev/null; then
                sudo systemctl stop $AGENT_SVC_NAME
            else
                sudo service $AGENT_SVC_NAME stop
            fi
    else
        return 0
    fi
}

# restart agent if running.
restart_agent() {
    if which systemctl >/dev/null; then
        sudo systemctl restart $AGENT_SVC_NAME
    else
        sudo service $AGENT_SVC_NAME restart
    fi
}
