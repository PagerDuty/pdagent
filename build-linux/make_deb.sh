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

set -e

# do stuff in the script's directory.
basedir=$(dirname $0)
cd $basedir

# source common variables
. ./make_common.env

mkdir -p $2

if [ -z "$1" -o -z "$2" -o ! -d "$1" -o ! -d "$2" ]; then
    echo "Usage: $0 {path-to-gpg-home} {path-to-package-installation-root}"
    exit 2
fi
gpg_home="$1"
install_root="$2"
deb_install_root=$install_root/deb
[ -d "$deb_install_root" ] || mkdir -p $deb_install_root

sh make_package.sh deb

echo "Creating an installable local package repository..."
cp target/*.deb $deb_install_root/
cd $install_root
apt-ftparchive packages deb | tee deb/Packages | gzip -9 >deb/Packages.gz
[ ! -e deb/Release ] || rm deb/Release
cat >/tmp/apt-ftparchive.conf <<EOF
APT {
  FTPArchive {
    Release {
      Architectures "all";
      # the below is required to make apt work with our trivial Debian repo.
      Codename "deb";
      Components "contrib";
      Label "PagerDuty, Inc.";
      Origin "PagerDuty, Inc.";
      Suite "stable";
    }
  }
}
EOF
apt-ftparchive -c /tmp/apt-ftparchive.conf release deb >Release
mv Release deb/
[ ! -e deb/Release.gpg ] || rm deb/Release.gpg
gpg --homedir $gpg_home --lock-never \
    --output deb/Release.gpg \
    --digest-algo SHA256 \
    --detach-sign --armor deb/Release

echo "Local install-worthy repository created at: $deb_install_root"

exit 0
