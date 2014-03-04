#
# See howto.txt for instructions.
#
# Copyright (c) 2013-2014, PagerDuty, Inc. <info@pagerduty.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the copyright holder nor the
#     names of its contributors may be used to endorse or promote products
#     derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

set -e  # fail on errors

# params
case "$1" in
  deb|rpm)
        ;;
  *)
        echo "Usage: $0 {deb|rpm}"
        exit 2
esac

echo = BUILD TYPE: $1

# ensure we're in the build directory
cd $(dirname "$0")

echo = cleaning build directories
rm -fr data target
mkdir data target


echo = /usr/bin/...
mkdir -p data/usr/bin
cp ../bin/pd-send data/usr/bin
cp ../bin/pd-zabbix data/usr/bin

echo = /usr/share/pdagent/bin
mkdir -p data/usr/share/pdagent/bin
cp ../bin/pdagentd.py data/usr/share/pdagent/bin

echo = /var/...
mkdir -p data/var/log/pdagent
mkdir -p data/var/lib/pdagent/db
mkdir -p data/var/lib/pdagent/outqueue

echo = /etc/...
mkdir -p data/etc/
cp ../conf/pdagent.conf data/etc/
mkdir -p data/etc/init.d
cp init-script.sh data/etc/init.d/pdagent
chmod 755 data/etc/init.d/pdagent

if [[ "$1" == "deb" ]]; then
    _PY_SITE_PACKAGES=data/usr/share/pyshared
else
    _PY_SITE_PACKAGES=data/usr/lib/python2.6/site-packages
fi

echo = python modules...
mkdir -p $_PY_SITE_PACKAGES
(cd .. && find pdagent -type d -exec mkdir build-linux/$_PY_SITE_PACKAGES/{} \;)
(cd .. && find pdagent -type f -name "*.py" -exec cp {} build-linux/$_PY_SITE_PACKAGES/{} \;)
(cd .. && find pdagent -type f -name "ca_certs.pem" -exec cp {} build-linux/$_PY_SITE_PACKAGES/{} \;)

if [[ "$1" == "deb" ]]; then
    echo = deb python-support...
    mkdir -p data/usr/share/python-support
    _PD_PUBLIC=data/usr/share/python-support/python-pdagent.public
    echo pyversions=2.6- > $_PD_PUBLIC
    echo >> $_PD_PUBLIC
    find $_PY_SITE_PACKAGES -type f -name "*.py" | cut -c 5- >> $_PD_PUBLIC
    find $_PY_SITE_PACKAGES -type f -name "ca_certs.pem" | cut -c 5- >> $_PD_PUBLIC
fi

echo = FPM!
_FPM_DEPENDS="--depends sudo --depends python"
if [[ "$1" == "deb" ]]; then
    _FPM_DEPENDS="$_FPM_DEPENDS --depends python-support"
fi

cd target
fpm -s dir \
    -t $1 \
    --name "pdagent" \
    --version "0.6" \
    --architecture all \
    $_FPM_DEPENDS \
    --$1-user root \
    --$1-group root \
    --config-files /etc/pdagent.conf \
    --post-install ../$1/postinst \
    --pre-uninstall ../$1/prerm \
    -C ../data \
    etc usr var

exit 0

