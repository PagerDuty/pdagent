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

test -x $EXEC || exit 1

get_pid() {
  test ! -e $PID_FILE || cat $PID_FILE
}

is_running() {
  pid=$(get_pid)
  if test -n "$pid"; then
   ps -p $pid >/dev/null 2>&1
  else
    return 1
  fi
}

setup() {
  test -d $PID_DIR || {
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
    sudo -u pdagent $EXEC $PID_FILE
    exit_code=$?
    test $exit_code -eq 0 || return $exit_code
  }
  echo "Started."
  return 0
}

stop() {
  echo "Stopping pdagent..."
  is_running && {
    sudo -u pdagent kill -TERM $(get_pid)
    exit_code=$?
    test $exit_code -eq 0 || return $exit_code
    c=30  # wait up to 30sec for process to stop running.
    while test $c -gt 0; do
      if is_running; then
        sleep 1
        c=$(( $c - 1 ))
      else
        c=0
      fi
    done
    ! is_running || {
      echo "pdagent has still not stopped."
      return 1
    }
  }
  echo "Stopped."
  return 0
}

status() {
  if $(is_running); then
    echo "pdagent (pid $(get_pid)) is running."
  else
    echo "pdagent is not running."
  fi
}

cleanup() {
  stop && {
    test ! -e $PID_FILE || {
      echo "Removing pid file..."
      echo sudo -u pdagent /bin/rm $PID_FILE
    }
  }
  return 0
}

options=
commands=

for w in "$@"; do
  case $w in
  -*)
    options="$options $w"
    ;;
  *)
    commands="$commands $w"
  esac
done

for w in $options $commands; do
  case $w in
  --clean|-clean|-c)
    cleanup
    ;;
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
    echo "Unrecognized argument: $w" >&2
    exit 1
  esac
done
