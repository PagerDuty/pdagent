#
# Agent config dirs for different layouts.
#

import os
import sys


_PRODUCTION_MAIN_DIRS = [
    "/usr/bin", "/etc/init.d",  # Linux
    ]


def _linux_production_dirs():
    d = {
        "pidfile_dir": "/var/run",
        "log_dir": "/var/log/pdagent",
        "data_dir": "/var/lib/pdagent",
        }
    return "/etc/pd-agent", d


def _dev_project_dirs(dev_proj_dir):
    dev_tmp_dir = os.path.join(dev_proj_dir, "tmp")
    d = {
        "pidfile_dir": dev_tmp_dir,
        "log_dir": dev_tmp_dir,
        "data_dir": dev_tmp_dir,
        }
    return os.path.join(dev_proj_dir, "conf"), d


def getconfdirs(main_dir, dev_proj_dir):
    if dev_proj_dir is None:
        # Production layout
        # Check that the python main program is really in production layout.
        # Production testing is done using `import pdagent` and this can give
        # us a false positive due to mix & match or user PYTHONPATH hacking.
        if not main_dir in _PRODUCTION_MAIN_DIRS:
            print "Program in unexpected directory:", main_dir
            print "(another agent may be installed and/or in the python path)"
            sys.exit(1)
        conf_dir, default_dirs = _linux_production_dirs()
    else:
        # Development layout
        conf_dir, default_dirs = _dev_project_dirs(dev_proj_dir)

    default_dirs["outqueue_dir"] = \
        os.path.join(default_dirs["data_dir"], "outqueue")
    conf_file = os.path.join(conf_dir, "config.cfg")

    return conf_file, default_dirs
