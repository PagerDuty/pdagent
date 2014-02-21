#!/bin/sh
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
#
# chkconfig: 2345 99 1
# description: PagerDuty Agent daemon process.
#

### BEGIN INIT INFO
# Provides:          pdagent
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: PagerDuty Agent
# Description:       PagerDuty Agent daemon process.
### END INIT INFO

EXEC=/usr/bin/pdagentd.py
PID_DIR=/var/run/pdagent
PID_FILE=$PID_DIR/pdagentd.pid

[ -x $EXEC ] || {
  echo "Missing pdagent executable: $EXEC" >&2
  exit 1
}

get_pid() {
  [ -e $PID_FILE ] && cat $PID_FILE
}

is_running() {
  pid=$(get_pid)
  [ -n "$pid" ] && ps -p $pid >/dev/null 2>&1
}

setup() {
  [ -d $PID_DIR ] || {
    sudo mkdir $PID_DIR || {
      echo "Error creating pid directory $PID_DIR" >&2
      exit 2
    }
    sudo chown -R pdagent:pdagent $PID_DIR || {
      echo "Error changing ownership of pid directory $PID_DIR" >&2
      exit 2
    }
  }
}

start() {
  echo "Starting pdagent..."
  setup
  is_running || {
    sudo -u pdagent $EXEC
    [ $? -eq 0 ] || return $?
  }
  echo "Started."
  return 0
}

stop() {
  echo "Stopping pdagent..."
  is_running && {
    sudo -u pdagent kill -TERM $(get_pid)
    [ $? -eq 0 ] || return $?
    c=30  # wait up to 30sec for process to stop running.
    while [ $c -gt 0 ]; do
      if is_running; then
        sleep 1
        c=$(( $c - 1 ))
      else
        c=0
      fi
    done
    is_running && {
      echo "pdagent has still not stopped."
      return 1
    }
  }
  echo "Stopped."
  return 0
}

status() {
  if is_running; then
    echo "pdagent (pid $(get_pid)) is running."
  else
    echo "pdagent is not running."
  fi
}

case $1 in
start)
  start
  ;;
stop)
  stop
  ;;
status)
  status
  ;;
restart)
  stop && start
  ;;
*)
  echo "Usage: $(basename "$0") {start|stop|restart|status}" >&2
  exit 1
esac
