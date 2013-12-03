
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
#   sh deb.sh
#
# Testing the .deb:
#
#   vagrant ssh agent-lucid32
#
#   # project directory should be mounted in the VM at /vagrant
#   sudo dpkg -i /vagrant/pdagent_0.1_all.deb
#   which agent.py
#   which pd-send.py
#   python -c "import pdagent; print pdagent.__file__"
#   sudo apt-get --yes remove pdagent
#



set -e

rm -fr build-deb
mkdir build-deb

echo bin...
mkdir -p build-deb/usr/bin
cp bin/*.py build-deb/usr/bin
chmod +x build-deb/usr/bin/*.py

echo pdagent...
mkdir -p build-deb/usr/share/pyshared
find pdagent -type d -exec mkdir build-deb/usr/share/pyshared/{} \;
find pdagent -type f -name "*.py" -exec cp {} build-deb/usr/share/pyshared/{} \;
cp pdagent-0.1.egg-info build-deb/usr/share/pyshared/

echo python-support...
mkdir -p build-deb/usr/share/python-support
cp python-pdagent.public build-deb/usr/share/python-support/
find build-deb/usr/share/pyshared | grep "egg" | cut -c 10- >> build-deb/usr/share/python-support/python-pdagent.public
find build-deb/usr/share/pyshared | grep "py$" | cut -c 10- >> build-deb/usr/share/python-support/python-pdagent.public

echo ---- python-pdagent.public:
cat build-deb/usr/share/python-support/python-pdagent.public
echo ----


fpm -s dir -t deb \
    -n "pdagent" \
    -v "0.1" \
    -a all \
    -d python \
    -d python-support \
    -C build-deb \
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
