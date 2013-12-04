#
# Build script for agent.
#

import sys
import subprocess


def runUnitTests(target, source, env):
    """Run unit tests."""

    print "\n+++ Running unit tests in current directory"
    retCode = subprocess.call(['python', 'run-tests.py'])
    if retCode:
        print "Unit tests failed!"
    return retCode

env = Environment()
env.Alias('all', ['.'])

Help("""
Usage: scons command [command...]
where supported commands include:
all         Runs all commands.
help        Prints this message.
test        Runs unit tests.
""")

unitTestTask = env.Command('test', None, Action(runUnitTests, "\nRunning unit tests"))
