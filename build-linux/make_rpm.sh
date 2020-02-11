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

set -x

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
rpm_install_root=$install_root/rpm
[ -d "$rpm_install_root" ] || mkdir -p $rpm_install_root

echo "Setting up GPG information for RPM..."
# fingerprint to use for signing = first fingerprint in GPG keyring
fp=$(gpg --homedir $gpg_home --no-tty --lock-never --fingerprint | \
     grep '=' | \
     head -n1 | \
     cut -d= -f2 | \
     tr -d ' ')
cat >$HOME/.rpmmacros <<EOF
%_signature gpg
%_gpg_path $gpg_home
%_gpg_name $fp
EOF

sh make_package.sh rpm

echo "Creating an installable local package repository..."
cp target/*.rpm $rpm_install_root/
cd $rpm_install_root
# the next command cleanly (re)creates repodata and repodata/*
createrepo --simple-md-filenames .

echo "Local install-worthy repository created at: $rpm_install_root"

exit 0
