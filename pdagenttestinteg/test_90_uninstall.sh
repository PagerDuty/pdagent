#
# Uninstalls the agent.
#

. $(dirname $0)/util.sh

set -e
set -x

# get agent to run.
test -n "$(agent_pid)" || start_agent

# uninstall agent.
case $(os_type) in
  debian)
    sudo apt-get --yes remove pdagent
    ;;
  redhat)
    sudo rpm -e pdagent
    ;;
  *)
    echo "Unknown os_type " $(os_type) >&2
    exit 1
esac

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
test -z "$(agent_pid)"
