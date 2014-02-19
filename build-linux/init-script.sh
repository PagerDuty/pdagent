#!/bin/sh
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
  echo "Unrecognized argument: $1" >&2
  echo "Usage: $(basename "$0") {start|stop|restart|status}" >&2
  exit 1
esac
