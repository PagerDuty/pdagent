

import ConfigParser
import logging
import os
import re
import sys


_valid_log_levels = \
    ['DEBUG', 'INFO', 'ERROR', 'WARN', 'WARNING', 'CRITICAL', 'FATAL']


_DEFAULT_LOG_LEVEL = logging.INFO
_DEFAULT_CHECK_FREQ_SEC = 60
_DEFAULT_CLEANUP_FREQ_SEC = 60 * 60 * 3  # clean up every 3 hours.


_dev_layout = False
_default_dirs = None
_main_config = None


def is_dev_layout():
    return _dev_layout


def get_conf_dirs():
    return _default_dirs


def get_main_config():
    return _main_config


def get_outqueue_dir():
    return os.path.join(_default_dirs["data_dir"], "outqueue")


def _load_config(conf_file, default_dirs):
    global _default_dirs, _main_config
    assert not _main_config, "Cannot load config twice!"
    _default_dirs = default_dirs

    if not os.access(conf_file, os.R_OK):
        print 'Unable to read the config file at ' + conf_file
        print 'Agent will now quit'
        sys.exit(1)

    # Config defaults
    cfg = {}
    cfg['check_freq_sec'] = _DEFAULT_CHECK_FREQ_SEC
    cfg['cleanup_freq_sec'] = _DEFAULT_CLEANUP_FREQ_SEC

    # Load config file
    try:
        config = ConfigParser.SafeConfigParser()
        config.read(conf_file)
    except ConfigParser.Error, e:
        print 'Error loading config:', e.message
        print 'Agent will now quit'
        sys.exit(1)

    # Convert loaded config into "Section.Option" entries
    if not config.has_section("Main"):
        print "Config is missing [Main] section"
        print 'Agent will now quit'
        sys.exit(1)
    for option in config.options("Main"):
        cfg[option] = config.get("Main", option)

    # Check for required keys
    if not "event_api_url" in cfg:
        print "Config is missing 'event_api_url'"
        print "Agent will now quit"
        sys.exit(1)

    # Convert log level
    if "log_level" in cfg:
        custom_log_level = cfg["log_level"].upper()
        if custom_log_level in _valid_log_levels:
            cfg["log_level"] = getattr(logging, custom_log_level)
        else:
            del cfg["log_level"]
    if not "log_level" in cfg:
        cfg["log_level"] = _DEFAULT_LOG_LEVEL

    # Check that default config values have been changed (only core config)
    if cfg['event_api_url'] == 'http://example.pagerduty.com':
        print 'You have not modified config file:', conf_file
        print 'Agent will now quit'
        sys.exit(1)

    # Check to make sure pd_url format is correct
    if re.match(
            'http(s)?(\:\/\/)[a-zA-Z0-9_\-]+\.(pagerduty.com)',
            cfg['event_api_url']
            ) == None:
        print 'Your event_api_url is incorrect. It needs to be in the form' \
            ' https://example.pagerduty.com'
        print 'Agent will now quit'
        sys.exit(1)

    _main_config = cfg


def _load():
    # (Re)figure out if we're in dev or prod layout
    # Main script logic must match this!!!
    main_module = sys.modules["__main__"]
    main_dir = os.path.dirname(os.path.realpath(main_module.__file__))
    dev_proj_dir = os.path.dirname(main_dir)
    if sys.path[-1] != dev_proj_dir:
        dev_proj_dir = None
    global _dev_layout
    _dev_layout = bool(dev_proj_dir)
    from pdagent.confdirs import getconfdirs
    conf_file, default_dirs = getconfdirs(main_dir, dev_proj_dir)
    _load_config(conf_file, default_dirs)

# Load config when this module is imported
_load()
