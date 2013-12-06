
# HOWTO:
#
# Dev Setup:
#
#   vagrant ssh agent-centos64
#
#   sudo yum install rpm-build
#   sudo yum install ruby-devel
#   sudo gem install fpm
#
#
# Building the .rpm:
#
#   vagrant ssh agent-centos64
#
#   rm -fr agent
#   cp -r /vagrant agent
#   cd agent/build-deb/
#   rm pdagent-0.1-1.noarch.rpm
#   sh makerpm.sh
#
# Testing the .rpm:
#
#   vagrant ssh agent-centos64
#
#   # project directory should be mounted in the VM at /vagrant
#   sudo rpm -i /vagrant/build-deb/pdagent-0.1-1.noarch.rpm
#   which agent.py
#   which pd-send.py
#   python -c "import pdagent; print pdagent.__file__"
#   sudo rpm -e pdagent
#



set -e  # fail on errors

rm -fr data
mkdir data

echo bin...
mkdir -p data/usr/bin
cp ../bin/*.py data/usr/bin

echo var...
mkdir -p data/var/log/pdagent
mkdir -p data/var/lib/pdagent/outqueue

echo pdagent...
mkdir -p data/usr/lib/python2.6/site-packages
(cd .. && find pdagent -type d -exec mkdir build-deb/data/usr/lib/python2.6/site-packages/{} \;)
(cd .. && find pdagent -type f -name "*.py" -exec cp {} build-deb/data/usr/lib/python2.6/site-packages/{} \;)

fpm -s dir -t rpm \
    --name "pdagent" \
    --version "0.1" \
    --architecture all \
    --depends python \
    -C data \
    usr

