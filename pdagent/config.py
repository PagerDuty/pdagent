

import ConfigParser
import logging
import os
import sys
import time

from pdagent.confdirs import getconfdirs
from pdagent.thirdparty.filelock import FileLock


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

    def get_queue(self, dequeue_enabled=False):
        from pdagent.pdqueue import PDQueue
        if dequeue_enabled:
            from pdagent.jsonstore import JsonStore
            backoff_db = JsonStore("backoff", self.default_dirs["db_dir"])
            backoff_secs = [
                int(s.strip()) for s in
                self.main_config["backoff_secs"].split(",")
            ]
        else:
            backoff_db = None
            backoff_secs = None
        return PDQueue(
            lock_class=FileLock,
            queue_dir=self.default_dirs["outqueue_dir"],
            time_calc=time,
            max_event_bytes=self.main_config["max_event_bytes"],
            backoff_db=backoff_db,
            backoff_secs=backoff_secs
        )

_valid_log_levels = \
    ['DEBUG', 'INFO', 'ERROR', 'WARN', 'WARNING', 'CRITICAL', 'FATAL']


_CONFIG_DEFAULTS = {
    "log_level": "INFO",
    "send_interval_secs": 60,
    "send_event_timeout_sec": 30,
    "cleanup_interval_secs": 60 * 60 * 3,  # clean up every 3 hours.
    "cleanup_threshold_secs": 60 * 60 * 24 * 7,  # clean up events older than 1 wk.
    "max_event_bytes": 4 * 1024 * 1024,  # 4MB limit on request data sent out.
    }


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

    conf_file, default_dirs = getconfdirs(main_dir, dev_proj_dir)

    if not os.access(conf_file, os.R_OK):
        raise SystemExit(
            "Unable to read the config file at: %s\nAgent will now quit"
            % conf_file
            )

    # Main config defaults
    cfg = dict(_CONFIG_DEFAULTS)

    # Load config file
    try:
        config = ConfigParser.SafeConfigParser()
        config.read(conf_file)
    except ConfigParser.Error, e:
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

    # Convert log level
    log_level = cfg["log_level"].upper()
    if log_level in _valid_log_levels:
        cfg["log_level"] = getattr(logging, log_level)
    else:
        raise SystemExit(
            "Bad log_level in config file: %s\nAgent will now quit"
            % conf_file
            )

    # parse integer values.
    for key in [
            "send_interval_secs",
            "cleanup_interval_secs",
            "cleanup_threshold_secs",
            "send_event_timeout_sec",
            "max_event_bytes",
            ]:
        try:
            cfg[key] = int(cfg[key])
        except ValueError:
            print 'Bad %s in config file: %s' % (key, conf_file)
            print 'Agent will now quit'
            sys.exit(1)

    _agent_config = AgentConfig(dev_layout, default_dirs, cfg)

    return _agent_config
