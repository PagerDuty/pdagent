#
# Uninstalls the agent.
#

# only run test on debian installations.
[ -e /etc/debian_version ] || exit 0

. $(dirname $0)/util.sh

set -e
set -x

# get agent to run.
test -n "$(agent_pid)" || start_agent

# uninstall agent.
sudo apt-get --yes remove pdagent

# for the 'negative = success' commands below, (i.e. we expect the command to
# fail), we are going to remove the 'set -e' condition, and check the exit code
# ourselves.
set +e

# check uninstallation status -- no components must be present.
# no binaries...
which $BIN_PD_SEND
test $? -ne 0 || exit 1
# no libraries...
python -c "import pdagent; print pdagent.__file__" && exit 1
test $? -ne 0 || exit 1
# no configuration files...
test ! -e $CONFIG_FILE

# ensure that agent is not running.
# TODO agent still runs. Stop it in `prerm`.
sudo service $SVC_AGENT status
test $? -ne 0 || exit 1
