#
# Build script for agent.
#

import os
import subprocess
import sys


def create_dist(target, source, env):
    """Create distributable for agent."""
    # TODO copy packages, documentation?
    pass


def create_packages(target, source, env):
    """Create installable packages for supported operating systems."""
    ret_code = 0
    virts = env.get("virts")

    debian_vms = [
        v for v in virts
        if v.find("lucid") != -1 or v.find("precise") != -1
    ]
    if debian_vms:
        ret_code += _create_deb_package(debian_vms)

    redhat_vms = [v for v in virts if v.find("centos") != -1]
    if redhat_vms:
        ret_code += _create_rpm_package(redhat_vms)

    return ret_code


def run_integration_tests(target, source, env):
    """Run integration tests on running virts."""
    source_paths = [s.path for s in source]
    test_runner_file = _generate_remote_test_runner_file(
        source_paths,
        lambda f: f.startswith("test_") and f.endswith(".sh"),
        executable="sh")
    return _run_on_virts("sh %s" % test_runner_file, env.get("virts"))


def run_unit_tests(target, source, env):
    """Run unit tests on specific / all running virts."""
    source_paths = [s.path for s in source]
    remote_test_runner = os.path.join(remote_project_root, "run-tests.py")
    test_paths = _get_file_paths_recursive(
            source_paths,
            lambda f: f.startswith("test_") and f.endswith(".py"))
    test_paths.sort()
    remote_test_command = ["python", remote_test_runner]
    remote_test_command.extend(\
        [os.path.join(remote_project_root, t) for t in test_paths])
    return _run_on_virts(" ".join(remote_test_command), env.get("virts"))


def run_unit_tests_local(target, source, env):
    """Run unit tests on current machine."""
    source_paths = [s.path for s in source]
    test_paths = _get_file_paths_recursive(
        source_paths,
        lambda f: f.startswith("test_") and f.endswith(".py"))
    test_paths.sort()
    test_command = [sys.executable, "run-tests.py"]
    test_command.extend(test_paths)
    return subprocess.call(test_command)


def start_virtual_boxes(target, source, env):
    virts = env.get("virts", [])
    start_cmd = ["vagrant", "up"]
    start_cmd.extend(virts)
    return subprocess.call(start_cmd)


def _create_deb_package(virts):
    # Assuming that all requisite packages are available.
    # (see build-linux/howto.txt)
    print "\nCreating .deb package..."
    return subprocess.call(['sh', 'make.sh', 'deb'], cwd=build_linux_dir)


def _create_rpm_package(virts):
    # create a temporary file to cd to required directory and make rpm.
    make_file = os.path.join(tmp_dir, "make_rpm")
    _create_text_file(make_file, [
        'set -e',
        'cd %s' % os.path.join(remote_project_root, build_linux_dir),
        'sh make.sh rpm'
    ])
    make_file_on_vm = os.path.join(remote_project_root, make_file)
    print "\nCreating .rpm package..."
    return _run_on_virts("sh %s" % make_file_on_vm, virts)


def _generate_remote_test_runner_file(
    source_paths,
    test_filename_matcher,
    executable=sys.executable):

    env.Execute(Mkdir(tmp_dir))
    test_runner_file = os.path.join(tmp_dir, "run_tests")

    test_files = _get_file_paths_recursive(source_paths, test_filename_matcher)
    # these are under the remote project root dir on virtual boxes
    test_run_paths = [os.path.join(remote_project_root, t) for t in test_files]

    run_commands = ["e=0"]
    for test in test_run_paths:
        run_commands.append(" ".join([executable, test]))
        run_commands.append("e=$(( $e + $? ))")
    run_commands.append("exit $e")

    _create_text_file(test_runner_file, run_commands)

    return os.path.join(remote_project_root, test_runner_file)


def _get_file_paths_recursive(source_paths, filename_matcher):
    dirs_traversed = set()
    files = set()

    def _add_files(dir_path):
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
                _add_files(src)
        else:
            if filename_matcher(os.path.basename(src)):
                files.add(src)
    return list(files)


def _create_text_file(filepath, data):
    #TODO this doesn't work -- 'Textfile' is not recognized.
    #     env.Textfile(
    #         target=test_runner_file,
    #         source=run_commands)
    out = open(filepath, "w")
    out.write(os.linesep.join(data))
    out.close()


def _get_arg_values(key, default=None):
    values = [v for k, v in ARGLIST if k == key]
    if not values and default:
        values = default
    return values


def _get_virt_names():
    return [v.split()[0] for v in \
        subprocess \
        .check_output(["vagrant", "status"]) \
        .splitlines() \
        if (v.startswith("agent-minimal-") and v.find(" running (") >= 0)]


def _run_on_virts(remote_command, virts=None):
    exit_code = 0
    if not virts:
        virts = _get_virt_names()
    for virt in virts:
        command = ["vagrant", "ssh", virt, "-c", remote_command]
        print "Running on %s..." % virt
        exit_code += subprocess.call(command)
    return exit_code


env = Environment()

env.Help("""
Usage: scons [command [command...]]
where supported commands are:
all                 Runs all commands.
build               Runs unit tests on virtual machines, creates packages
                    and then runs integration tests on virtual machines.
                    This is the default command if none is specified.
--clean|-c          Removes generated artifacts.
dist                Creates distributable artifacts for agent.
package             Creates installable packages for supported OS
                    distributions.
start-virt          Starts configured virtual machines, installing them
                    first if required.
                    Specific virtual machines can be started by providing
                    them as arguments, multiple times if required.
                    e.g.
                    scons start-virt start-virt=agent-lucid32
test                Runs unit tests on all running virtual machines.
                    By default, runs all tests in `pdagenttest` recursively.
                    (Test files should be named in the format `test_*.py`.)
                    Specific unit tests can be run by providing them as
                    arguments to this option, multiple times if required.
                    Both test files and test directories are supported.
                    e.g.
                    scons test test=pdagenttest/test_foo.py
test-integration    Runs integration tests on all running virtual machines.
                    By default, runs all tests in `pdagenttestinteg`
                    recursively. (Test files should be named in the format
                    `test_*.sh`.)
                    Like the 'test' command, specific tests can be run by
                    providing them as arguments to this option, multiple
                    times if required. Both test files and test directories
                    are supported.
test-local          Runs unit tests on the local machine.
                    Please see 'test' command for more details.
test-vm             Runs unit tests on the specified virtual machine,
                    starting it if required.
                    Virtual machines are specified by providing them as
                    arguments, multiple times if required.
                    Specific unit tests to run can be specified as `test`
                    arguments if required.
                    e.g.
                    scons test-vm test-vm=agent-lucid32 test=test_foo.py
""")

build_linux_dir = "build-linux"
target_dir = "target"
tmp_dir = os.path.join(target_dir, "tmp")
dist_dir = "dist"
remote_project_root = os.sep + "vagrant"  # TODO windows

unit_test_local_task = env.Command(
    "test-local",
    _get_arg_values("test", ["pdagenttest"]),
    env.Action(run_unit_tests_local, "\n--- Running unit tests locally"))

start_virts_task = env.Command(
    "start-virt",
    None,
    env.Action(start_virtual_boxes, "\n--- Starting virtual boxes"),
    virts=_get_arg_values("virt"))

unit_test_task = env.Command(
    "test",
    _get_arg_values("test", ["pdagenttest"]),
    env.Action(run_unit_tests,
        "\n--- Running unit tests on virtual boxes"),
    virts=_get_arg_values("virt"))
env.Requires(unit_test_task, start_virts_task)

create_packages_task = env.Command(
    "package",
    None,
    env.Action(create_packages, "\n--- Creating install packages"),
    virts=_get_arg_values("virt"))
env.Requires(create_packages_task, [unit_test_task, start_virts_task])

integration_test_task = env.Command(
    "test-integration",
    _get_arg_values("test", ["pdagenttestinteg"]),
    env.Action(run_integration_tests,
        "\n--- Running integration tests on virtual boxes"),
    virts=_get_arg_values("virt"))
env.Requires(integration_test_task, [start_virts_task])

dist_task = env.Command(
    "dist",
    None,
    env.Action(create_dist, "\n--- Creating distributables"))
env.Requires(dist_task, [create_packages_task, integration_test_task])

# specify directories to be cleaned up for various targets
env.Clean([unit_test_task, integration_test_task], tmp_dir)
env.Clean([create_packages_task], target_dir)
env.Clean([dist_task], dist_dir)

build_task = env.Alias("build",\
    [unit_test_task, create_packages_task, integration_test_task])
env.Alias("all", ["."])

# task to run if no command is specified.
if env.GetOption("clean"):
    # workaround to get 'clean' to clean everything, and
    # not just the output of the usual default target.
    env.Default(".")
else:
    env.Default(build_task)
