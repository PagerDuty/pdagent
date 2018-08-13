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

# source common variables
. ./make_common.env

# params
pkg_type=""

print_usage_and_exit() {
    echo "Usage: $0 {deb|rpm}"
    exit 2
}

if [ $# -ne 1 ]; then
    print_usage_and_exit
fi

case "$1" in
    deb|rpm)
        pkg_type=$1
        ;;
    *)
        print_usage_and_exit
esac

echo = BUILD TYPE: $pkg_type

# ensure we're in the build directory
cd $(dirname "$0")

_VERSION=$(grep '__version__\s*=\s*".*"' ../pdagent/__init__.py \
    | cut -d \" -f2)
if [ -z "$_VERSION" ]; then
    echo "Could not find Agent version in source."
    exit 1
fi

echo = cleaning build directories
rm -fr data target
mkdir data target

echo = /usr/bin/...
mkdir -p data/usr/bin
cp ../bin/pd-* data/usr/bin

echo = /usr/share/pdagent/bin
mkdir -p data/usr/share/pdagent/bin
cp ../bin/pdagentd.py data/usr/share/pdagent/bin

echo = /var/...
mkdir -p data/var/log/pdagent
mkdir -p data/var/lib/pdagent/db
mkdir -p \
    data/var/lib/pdagent/outqueue/pdq \
    data/var/lib/pdagent/outqueue/tmp \
    data/var/lib/pdagent/outqueue/err \
    data/var/lib/pdagent/outqueue/suc
mkdir -p data/var/lib/pdagent/scripts
# stage sysV & systemd service files for pkg postinst
cp pdagent.init data/var/lib/pdagent/scripts/pdagent.init
cp pdagent.service data/var/lib/pdagent/scripts/pdagent.service

echo = /etc/...
mkdir -p data/etc/
cp ../conf/pdagent.conf data/etc/

if [ "$pkg_type" = "deb" ]; then
    _PY_SITE_PACKAGES=data/usr/lib/python2.7/dist-packages
else
    _PY_SITE_PACKAGES=data/usr/lib/python2.6/site-packages
    _PY27_SITE_PACKAGES=data/usr/lib/python2.7/site-packages
fi

echo = python modules...
mkdir -p $_PY_SITE_PACKAGES
cd ..
find pdagent -type d -exec mkdir -p build-linux/$_PY_SITE_PACKAGES/{} \;
find pdagent -type f \( -name "*.py" -o -name "ca_certs.pem" \) \
    -exec cp {} build-linux/$_PY_SITE_PACKAGES/{} \;
cd -

# copy the libraries for python2.7 rpm users
if [ "$pkg_type" = "rpm" ]; then
    mkdir -p "$_PY27_SITE_PACKAGES"
    cp -r $_PY_SITE_PACKAGES/* "$_PY27_SITE_PACKAGES"
fi

echo = FPM!
_FPM_DEPENDS="--depends sudo --depends python"

_SIGN_OPTS=""
if [ "$pkg_type" = "rpm" ]; then
    _SIGN_OPTS="--rpm-sign"
fi

_POST_TRANS_OPT=""
if [ "$pkg_type" = "rpm" ]; then
    _POST_TRANS_OPT="--rpm-posttrans ../rpm/posttrans"
fi

cd target

_DESC="The PagerDuty Agent package
The PagerDuty Agent is a helper program that you install on your
monitoring system to integrate your monitoring tools with PagerDuty."
if [ "$pkg_type" = "deb" ]; then
    _PKG_MAINTAINER="Package Maintainer"
else
    _PKG_MAINTAINER="RPM Package Maintainer"
fi
_PKG_MAINTAINER="$_PKG_MAINTAINER (PagerDuty, Inc.) <packages@pagerduty.com>"
if [ "$pkg_type" = "rpm" ]; then
    source /opt/rh/rh-ruby23/enable
    FPM=/opt/rh/rh-ruby23/root/usr/local/share/gems/gems/fpm-$FPM_VERSION/bin/fpm
else
    FPM=fpm
fi

$FPM -s dir \
     -t $pkg_type \
     --name "pdagent" \
     --description "$_DESC" \
     --version "$_VERSION" \
     --architecture all \
     --url "http://www.pagerduty.com" \
     --license 'Open Source' \
     --vendor 'PagerDuty, Inc.' \
     --maintainer "$_PKG_MAINTAINER" \
     $_FPM_DEPENDS \
     $_SIGN_OPTS \
     --${pkg_type}-user root \
     --${pkg_type}-group root \
     --config-files /etc/pdagent.conf \
     --before-install ../$pkg_type/preinst \
     --after-install ../$pkg_type/postinst \
     --before-remove ../$pkg_type/prerm \
     --after-remove ../$pkg_type/postrm \
     $_POST_TRANS_OPT \
     -C ../data \
     etc usr var

exit 0
