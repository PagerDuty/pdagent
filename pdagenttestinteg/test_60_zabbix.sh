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

# stop agent
test -z "$(agent_pid)" || stop_agent

# zabbix command line must enqueue correctly
test_zabbix_trigger() {

  # clear outqueue
  test $(ls $OUTQUEUE_DIR | wc -l) -eq 0 || sudo rm -r $OUTQUEUE_DIR/*

  pd-zabbix.py $SVC_KEY trigger "name:Zabbix server has just been restarted
id:13502
status:PROBLEM
hostname:Zabbix server
ip:127.0.0.1
value:1
event_id:70
severity:High"

  test $(ls $OUTQUEUE_DIR | wc -l) -eq 1

  diff -q $OUTQUEUE_DIR/pdq_*.txt $(dirname $0)/test_60_zabbix.pdq1.txt

}

test_zabbix_resolve() {

  # clear outqueue
  test $(ls $OUTQUEUE_DIR | wc -l) -eq 0 || sudo rm -r $OUTQUEUE_DIR/*

  pd-zabbix.py $SVC_KEY resolve "name:Zabbix server has just been restarted
id:13502
status:OK
hostname:Zabbix server
ip:127.0.0.1
value:0
event_id:126
severity:High"
  
  test $(ls $OUTQUEUE_DIR | wc -l) -eq 1

  diff -q $OUTQUEUE_DIR/pdq_*.txt $(dirname $0)/test_60_zabbix.pdq2.txt

}

test_zabbix_trigger
test_zabbix_resolve
