#
# Installs the agent.
#

. $(dirname $0)/util.sh

set -e
set -x

# install agent.
case $(os_type) in
  debian)
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

# check that there is a guid file created.
test -e $DATA_DIR/guid.txt
