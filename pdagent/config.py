

import ConfigParser
import logging
import os
import re
import sys


_valid_log_levels = \
    ['DEBUG', 'INFO', 'ERROR', 'WARN', 'WARNING', 'CRITICAL', 'FATAL']


def loadConfig(conf_file, default_dirs):

    if not os.access(conf_file, os.R_OK):
        print 'Unable to read the config file at ' + conf_file
        print 'Agent will now quit'
        sys.exit(1)

    # General config
    cfg = dict(default_dirs)
    cfg['log_level'] = logging.INFO
    cfg['checkFreqSec'] = 60
    cfg['cleanupFreqSec'] = 60 * 60 * 3  # clean up every 3 hours.

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
    if type(cfg["log_level"]) is not int:
        custom_log_level = cfg["log_level"].upper()
        if custom_log_level in _valid_log_levels:
            cfg["log_level"] = getattr(logging, custom_log_level)

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

    return cfg
