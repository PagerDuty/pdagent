
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

echo pdagent...
mkdir -p data/usr/share/pyshared
(cd .. && find pdagent -type d -exec mkdir build-deb/data/usr/share/pyshared/{} \;)
(cd .. && find pdagent -type f -name "*.py" -exec cp {} build-deb/data/usr/share/pyshared/{} \;)
#cp pdagent-0.1.egg-info data/usr/share/pyshared/

echo python-support...
mkdir -p data/usr/share/python-support
echo pyversions=2.4- > data/usr/share/python-support/python-pdagent.public
echo >> data/usr/share/python-support/python-pdagent.public
find data/usr/share/pyshared -type f -name "*.py" | cut -c 5- >> data/usr/share/python-support/python-pdagent.public
#find data/usr/share/pyshared | grep "egg" | cut -c 10- >> data/usr/share/python-support/python-pdagent.public
#find data/usr/share/pyshared -name "*.py" | cut -c 10- >> data/usr/share/python-support/python-pdagent.public

echo ---- python-pdagent.public:
cat data/usr/share/python-support/python-pdagent.public
echo ----


fpm -s dir -t deb \
    -n "pdagent" \
    -v "0.1" \
    -a all \
    -d python \
    -d python-support \
    -C data \
    --post-install deb-postinst \
    usr

#    --prefix /usr \
#    --prefix /opt/pagerduty-agent \

#    $(SOURCEDIR)

#    -C src \
#    --deb-user pdagent


#fpm -s dir -t deb -n $(NAME) -v $(VERSION) -d "nodejs (>= 0)" -a all \
#         --prefix $(INSTALLDIR) --exclude .svn -C src $(SOURCEDIR)

# --config-files /etc/redis/redis.conf -v 2.6.10 ./src/redis-server=/usr/bin redis.conf=/etc/redis
