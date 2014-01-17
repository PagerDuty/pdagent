AGENT_USER=pdagent
BIN_PD_SEND=pd-send.py
CONFIG_FILE=/etc/pdagent/config.cfg
OUTQUEUE_DIR=/var/lib/pdagent/outqueue
AGENT_SVC_NAME=pd-agent
CHECK_FREQ_SEC=5
# The service key to use for testing commands like pd-send.py etc.
SVC_KEY=474248a48ee349aeb3f6c87a3ce779ff

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
