#
# Installs the agent.
#

. $(dirname $0)/util.sh

set -e
set -x

# install agent.
case $(os_type) in
  debian)
    # FIXME: Ubuntu 12.04 does not include python-support.
    # We need to test that it is pulled in automatically when
    # pdagent is installed from repo rather than from .deb
    sudo apt-get install python-support
    sudo dpkg -i /vagrant/build-linux/target/pdagent_0.1_all.deb
    ;;
  redhat)
    sudo rpm -i /vagrant/build-linux/target/pdagent-0.1-1.noarch.rpm
    ;;
  *)
    echo "Unknown os_type " $(os_type) >&2
    exit 1
esac

# check installation status.
which $BIN_PD_SEND
python -c "import pdagent; print pdagent.__file__"

# check that agent has started up.
test -n "$(agent_pid)"

# check that there is an agent id file created.
test -e $DATA_DIR/agent_id.txt
