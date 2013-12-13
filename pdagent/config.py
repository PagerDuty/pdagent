

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
    cfg['check_freq'] = 60

    # Config handling
    try:
        config = ConfigParser.ConfigParser()
        config.read(conf_file)

        # Core config
        cfg['event_api_url'] = config.get('Main', 'event_api_url')

        # Optional config
        if config.has_option('Main', 'log_level'):
            custom_log_level = config.get('Main', 'log_level').upper()
            if custom_log_level in _valid_log_levels:
                cfg['log_level'] = getattr(logging, custom_log_level)

    except ConfigParser.ParsingError, e:
        print 'Config file not found or incorrectly formatted'
        print 'Error:', e.message
        print 'Agent will now quit'
        sys.exit(1)

    except ConfigParser.Error, e:
        print 'Config error:', e.message
        print 'Agent will now quit'
        sys.exit(1)

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
