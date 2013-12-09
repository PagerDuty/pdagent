
# HOWTO:
#
# Dev Setup:
#
#   gem install fpm
#
#
# Building the .deb:
#
#   rm pdagent_0.1_all.deb
#   sh makedeb.sh
#
# Testing the .deb:
#
#   vagrant ssh agent-lucid32
#
#   # project directory should be mounted in the VM at /vagrant
#   sudo dpkg -i /vagrant/build-deb/pdagent_0.1_all.deb
#   which agent.py
#   which pd-send.py
#   python -c "import pdagent; print pdagent.__file__"
#   sudo apt-get --yes remove pdagent
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

echo etc...
mkdir -p data/etc/pd-agent/
cp ../conf/config.cfg data/etc/pd-agent/
#mkdir -p data/etc/init.d
#cp TODO/pd-agent data/etc/init.d/

echo pdagent...
mkdir -p data/usr/share/pyshared
(cd .. && find pdagent -type d -exec mkdir build-deb/data/usr/share/pyshared/{} \;)
(cd .. && find pdagent -type f -name "*.py" -exec cp {} build-deb/data/usr/share/pyshared/{} \;)

echo python-support...
mkdir -p data/usr/share/python-support
echo pyversions=2.6- > data/usr/share/python-support/python-pdagent.public
echo >> data/usr/share/python-support/python-pdagent.public
find data/usr/share/pyshared -type f -name "*.py" \
    | cut -c 5- >> data/usr/share/python-support/python-pdagent.public

echo ---- python-pdagent.public:
cat data/usr/share/python-support/python-pdagent.public
echo ----

echo FPM!
fpm -s dir -t deb \
    --name "pdagent" \
    --version "0.1" \
    --architecture all \
    --depends python \
    --depends python-support \
    --post-install deb-postinst \
    -C data \
    etc usr var

#    --prefix /usr \
#    --deb-user pdagent
# --config-files /etc/redis/redis.conf -v 2.6.10 ./src/redis-server=/usr/bin redis.conf=/etc/redis
