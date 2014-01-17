#
# Runs the agent through various states -- stop, restart etc.
#

. $(dirname $0)/util.sh

set -e
set -x

# restart / start agent.
pid1=$(agent_pid)  # may be empty if agent is not already running.

restart_agent || start_agent
pid2=$(agent_pid)
test -n "$pid2"
test "$pid2" != "$pid1"

stop_agent
pid3=$(agent_pid)
test -z "$pid3"  # ensures empty pid.

start_agent
pid4=$(agent_pid)
test -n "$pid4"
test $pid4 -ne $pid2
