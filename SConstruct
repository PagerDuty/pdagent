#
# Build script for agent.
#

import os
import subprocess
import sys


def cleanup(target, source, env):
    """Removes generated artifacts"""
    # TODO clean up.
    pass


def createDist(target, source, env):
    """Create distributable for agent."""
    # TODO create.
    pass


def createPackage(target, source, env):
    """Create installable packages for supported operating systems."""
    retCode = 0
    retCode += _createDebPackage()
    retCode += _createRpmPackage()
    return retCode


def runIntegrationTests(target, source, env):
    """Run integration tests."""
    # TODO run tests.
    pass


def runUnitTests(target, source, env):
    """Run unit tests."""
    source_paths = []
    for s in source:
        source_paths.append(s.path)
    test_files = _getFilePathsRecursive(
        source_paths,
        lambda f: f.startswith("test_") and f.endswith(".py"))
    test_files.sort()

    total = 0
    errs = 0
    test_env = os.environ.copy()
    test_env["PYTHONPATH"] = \
        test_env.get("PYTHONPATH", "") + os.pathsep + Dir(".").abspath
    for test_file in test_files:
        print >> sys.stderr, "FILE:", test_file
        exit_code = subprocess.call([sys.executable, test_file], env=test_env)
        total += 1
        errs += (exit_code != 0)
    print >> sys.stderr, "SUMMARY: %s total / %s error (%s)" \
        % (total, errs, sys.executable)
    return errs


def startVirtualBoxes(target, source, env):
    virts = env.get("virts", [])
    start_cmd = ["vagrant", "up"]
    start_cmd.extend(virts)
    return subprocess.call(start_cmd)


def _createDebPackage():
    # TODO create the package.
    print "\nCreating .deb package..."
    return 0


def _createRpmPackage():
    # TODO create the package.
    print "\nCreating .rpm package..."
    return 0


def _getFilePathsRecursive(source_paths, filename_matcher):
    dirs_traversed = set()
    files = set()

    def _addFiles(dir_path):
        dirs_traversed.add(dir_path)
        for dirname, subdirnames, filenames in os.walk(dir_path):
            for subdir in subdirnames:
                dirs_traversed.add(os.path.join(dirname, subdir))
            for filename in filenames:
                if filename_matcher(filename):
                    files.add(os.path.join(dirname, filename))

    for src in source_paths:
        if os.path.isdir(src):
            if not src in dirs_traversed:
                _addFiles(src)
        else:
            if filename_matcher(os.path.basename(src)):
                files.add(src)
    return list(files)


def _get_arg_values(key, default=None):
    values = [v for k, v in ARGLIST if k == key]
    if not values and default:
        values = default
    return values


Help("""
Usage: scons [command [command...]]
where supported commands are:
all                 Runs all commands.
build               Runs unit tests and builds agent components.
                    This is the default command if none is specified.
clean               Removes generated artifacts.
dist                Creates distributable artifacts for agent.
package             Creates installable packages for supported OS
                    distributions.
test                Runs unit tests.
                    By default, runs all tests in `pdagenttest` recursively.
                    (Test files should be named in the format `test_*.py`.)
                    Specific unit tests can be run by providing them as
                    arguments to this option, multiple times if required.
                    Both test files and test directories are supported.
                    e.g.
                    scons test=pdagenttest/test_foo.py test=pdagenttest/queue
test-integration    Runs integration tests.
""")


env = Environment()
env.Alias("all", ["."])


unitTestTask = env.Command(
    "test",
    _get_arg_values("test", ["pdagenttest"]),
    Action(runUnitTests, "\n--- Running unit tests"))

# TODO add a remote unit test task for running on vagrant images?

startVirtsTask = env.Command(
    "start-virt",
    None,
    Action(startVirtualBoxes, "\n--- Starting virtual boxes"),
    virts=_get_arg_values("start-virt"))

integrationTestTask = env.Command(
    "test-integration",
    _get_arg_values("test-integration", ["pdagenttest"]),  # TODO CHANGEME
    Action(runIntegrationTests, "\n--- Running integration tests"))
Requires(integrationTestTask, startVirtsTask)

buildTask = env.Alias("build", ["test"])

packageTask = env.Command(
    "package",
    None,
    Action(createPackage, "\n--- Creating install packages"))
Requires(packageTask, unitTestTask)

distTask = env.Command(
    "dist",
    None,
    Action(createDist, "\n--- Creating distributables"))
Requires(distTask, [unitTestTask, packageTask, integrationTestTask])

cleanTask = env.Command("clean", None, Action(cleanup, "\n--- Cleaning up"))

# task to run if no command specified.
Default(buildTask)
