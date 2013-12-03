
set -e

rm -fr build-deb
mkdir build-deb

echo bin...
mkdir -p build-deb/usr/bin
cp bin/*.py build-deb/usr/bin
chmod +x build-deb/usr/bin/*.py

echo pdagent...
mkdir -p build-deb/usr/share/pyshared/pdagent
cp pdagent/*.py build-deb/usr/share/pyshared/pdagent/
cp pdagent-0.1.egg-info build-deb/usr/share/pyshared/

echo python-support...
mkdir -p build-deb/usr/share/python-support
cp python-pdagent.public build-deb/usr/share/python-support/
find build-deb/usr/share/pyshared | grep "egg" | cut -c 10- >> build-deb/usr/share/python-support/python-pdagent.public
find build-deb/usr/share/pyshared | grep "py$" | cut -c 10- >> build-deb/usr/share/python-support/python-pdagent.public

cat build-deb/usr/share/python-support/python-pdagent.public


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
