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
import time
import uuid
from six.moves import configparser

from pdagent.confdirs import getconfdirs
from pdagent.thirdparty.filelock import FileLock


_ENQUEUE_FILE_MODE = 0o644  # rw-r--r--
_ENQUEUE_DEFAULT_UMASK = 0o022  # default umask for world-readability of files.


class AgentConfig:

    def __init__(self, dev_layout, default_dirs, main_config):
        self.dev_layout = dev_layout
        self.default_dirs = default_dirs
        self.main_config = main_config

    def is_dev_layout(self):
        return self.dev_layout

    def get_conf_dirs(self):
        return self.default_dirs

    def get_main_config(self):
        return self.main_config

    def get_outqueue_dir(self):
        return os.path.join(self.default_dirs["data_dir"], "outqueue")

    def get_db_dir(self):
        return os.path.join(self.default_dirs["data_dir"], "db")

    def get_agent_id_file(self):
        return os.path.join(self.default_dirs['data_dir'], "agent_id.txt")

    def get_agent_id(self):
        # returns None if agent_id is not available or readable
        fd = None
        try:
            fd = open(self.get_agent_id_file(), "r")
            return str(uuid.UUID(fd.readline().strip()))
        except (IOError, ValueError):
            return None
        finally:
            if fd:
                fd.close()

    def get_enqueuer(self):
        from pdagent.pdqueue import PDQEnqueuer
        return PDQEnqueuer(
            lock_class=FileLock,
            queue_dir=self.default_dirs["outqueue_dir"],
            time_calc=time,
            enqueue_file_mode=_ENQUEUE_FILE_MODE,
            default_umask=_ENQUEUE_DEFAULT_UMASK
            )

    def get_queue(self):
        from pdagent.pdqueue import PDQueue
        from pdagent.jsonstore import JsonStore
        backoff_db = JsonStore("backoff", self.default_dirs["db_dir"])
        backoff_interval = self.main_config["backoff_interval_secs"]
        retry_limit_for_possible_errors = \
            self.main_config["retry_limit_for_possible_errors"]
        counter_db = JsonStore("aggregates", self.default_dirs["db_dir"])
        return PDQueue(
            lock_class=FileLock,
            queue_dir=self.default_dirs["outqueue_dir"],
            time_calc=time,
            event_size_max_bytes=4 * 1024 * 1024,  # 4MB limit.
            backoff_db=backoff_db,
            backoff_interval=backoff_interval,
            retry_limit_for_possible_errors=retry_limit_for_possible_errors,
            counter_db=counter_db
            )


_agent_config = None


def load_agent_config():
    global _agent_config
    assert not _agent_config, "Cannot load config twice!"

    # (Re)figure out if we're in dev or prod layout
    # Main script logic must match this!!!
    main_module = sys.modules["__main__"]
    main_dir = os.path.dirname(os.path.realpath(main_module.__file__))
    dev_proj_dir = os.path.dirname(main_dir)
    if sys.path[-1] != dev_proj_dir:
        dev_proj_dir = None
    dev_layout = bool(dev_proj_dir)

    conf_file, default_dirs = getconfdirs(dev_proj_dir)

    if not os.access(conf_file, os.R_OK):
        raise SystemExit(
            "Unable to read the config file at: %s\nAgent will now quit"
            % conf_file
            )

    # Main config defaults
    cfg = dict()

    # Load config file
    try:
        config = configparser.SafeConfigParser()
        config.read(conf_file)
    except configparser.Error as e:
        raise SystemExit(
            "Error loading config: %s\nAgent will now quit"
            % e.message
            )

    # Convert Main section into dictionary entries
    if not config.has_section("Main"):
        raise SystemExit(
            "Config is missing [Main] section\nAgent will now quit"
            )
    for option in config.options("Main"):
        cfg[option] = config.get("Main", option)

    # parse integer values.
    for key in [
            "backoff_interval_secs",
            "cleanup_interval_secs",
            "cleanup_threshold_secs",
            "retry_limit_for_possible_errors",
            "send_interval_secs",
            ]:
        try:
            cfg[key] = int(cfg[key])
        except ValueError:
            print('Bad %s in config file: %s' % (key, conf_file))
            print('Agent will now quit')
            sys.exit(1)

    _agent_config = AgentConfig(dev_layout, default_dirs, cfg)

    return _agent_config
