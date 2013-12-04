#
# Build script for agent.
#

import sys
import subprocess


def runUnitTests(target = None, source = None, env = None):
    """Run unit tests."""

    print "\n+++ Running unit tests in current directory..."
    retCode = subprocess.call(['python', 'run-tests.py'])
    if retCode:
        print "Unit tests failed!"
        env.Exit(retCode)


env = Environment()
env.Alias('all', ['.'])
unitTestTask = env.Command('test', None, Action(runUnitTests, "\nRunning unit tests"))
