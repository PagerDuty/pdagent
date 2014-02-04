AGENT_USER=pdagent
BIN_PD_SEND=pd-send
CONFIG_FILE=/etc/pdagent/config.cfg
DATA_DIR=/var/lib/pdagent
OUTQUEUE_DIR=$DATA_DIR/outqueue
AGENT_SVC_NAME=pdagentd
CHECK_FREQ_SEC=5
# The service key to use for testing commands like pd-send.py etc.
SVC_KEY=CHANGEME

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
  sudo service $AGENT_SVC_NAME status | egrep -o 'pid [0-9]+' | cut -d' ' -f2
}

# start agent if not running.
start_agent() {
  if [ -z "$(agent_pid)" ]; then
    sudo service $AGENT_SVC_NAME start
  else
    return 1
  fi
}

# stop agent if running.
stop_agent() {
  if [ -n "$(agent_pid)" ]; then
    sudo service $AGENT_SVC_NAME stop
  else
    return 1
  fi
}

# restart agent if running.
restart_agent() {
  if [ -n "$(agent_pid)" ]; then
    sudo service $AGENT_SVC_NAME restart
  else
    return 1
  fi
}
