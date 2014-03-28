#
# Agent config dirs for different layouts.
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

import os
import sys


def _linux_production_dirs():
    d = {
        "pidfile_dir": "/var/run/pdagent",
        "log_dir": "/var/log/pdagent",
        "data_dir": "/var/lib/pdagent",
        }
    return "/etc", d


def _dev_project_dirs(dev_proj_dir):
    dev_tmp_dir = os.path.join(dev_proj_dir, "tmp")
    d = {
        "pidfile_dir": dev_tmp_dir,
        "log_dir": dev_tmp_dir,
        "data_dir": dev_tmp_dir,
        }
    return os.path.join(dev_proj_dir, "conf"), d


def getconfdirs(dev_proj_dir):
    if dev_proj_dir is None:
        conf_dir, default_dirs = _linux_production_dirs()
    else:
        # Development layout
        conf_dir, default_dirs = _dev_project_dirs(dev_proj_dir)

    default_dirs["outqueue_dir"] = \
        os.path.join(default_dirs["data_dir"], "outqueue")
    default_dirs["db_dir"] = \
        os.path.join(default_dirs["data_dir"], "db")
    conf_file = os.path.join(conf_dir, "pdagent.conf")

    return conf_file, default_dirs
