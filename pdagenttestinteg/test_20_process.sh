#
# Checks that agent processes events.
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
test $(ls $OUTQUEUE_DIR | wc -l) -eq 0 || sudo rm -r $OUTQUEUE_DIR/*

# modify agent check frequency so we wait for lesser time.
sudo sed -i "s#^\#queue_poll_interval_secs.*#queue_poll_interval_secs=$QUEUE_POLL_INTERVAL_SECS#" $CONFIG_FILE

# agent must flush out queue when it starts up.
test_startup() {
  $BIN_PD_SEND -k $SVC_KEY -t acknowledge -i test$$_1 -f key=value -f foo=bar
  $BIN_PD_SEND -k $SVC_KEY -t resolve -i test$$_1 -d "Testing"

  test $(ls $OUTQUEUE_DIR/pdq_* | wc -l) -eq 2

  start_agent
  test -n "$(agent_pid)"
  sleep $(($QUEUE_POLL_INTERVAL_SECS / 2))  # enough time for agent to flush the queue.
  test $(ls $OUTQUEUE_DIR | wc -l) -eq 2
  test $(ls $OUTQUEUE_DIR/suc_* | wc -l) -eq 2
}

# agent must flush out queue when it wakes up.
test_wakeup() {
  test $(ls $OUTQUEUE_DIR/* | wc -l) -eq 2
  $BIN_PD_SEND -k $SVC_KEY -t acknowledge -i test$$_2 -f baz=boo
  $BIN_PD_SEND -k $SVC_KEY -t resolve -i test$$_2 -d "Testing"
  # corrupt the latest enqueued file.
  echo "bad json" \
    | sudo tee $(ls $OUTQUEUE_DIR/pdq_* | tail -n1) >/dev/null

  sleep $(($QUEUE_POLL_INTERVAL_SECS * 3 / 2))  # sleep-time + extra-time for processing.
  # there must be one error file in outqueue; everything else must be cleared.
  test $(ls $OUTQUEUE_DIR/* | wc -l) -eq 4
  test $(ls $OUTQUEUE_DIR/err_* | wc -l) -eq 1
  test $(ls $OUTQUEUE_DIR/suc_* | wc -l) -eq 3
}

test_startup
test_wakeup
