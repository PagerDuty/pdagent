#
# Build script for agent.
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
import subprocess
import sys


_DEB_BUILD_VM = "agent-minimal-ubuntu1204"
_RPM_BUILD_VM = "agent-minimal-centos65"


def create_dist(target, source, env):
    """Create distributable for agent."""
    env.Execute(Mkdir(dist_dir))
    pkgs = [p.path for p in env.Glob(os.path.join(target_dir, "*.*"))]
    cp_pkgs_cmd = ["cp"]
    cp_pkgs_cmd.extend(pkgs)
    cp_pkgs_cmd.append(dist_dir)
    return subprocess.call(cp_pkgs_cmd)


def create_packages(target, source, env):
    """Create installable packages for supported operating systems."""
    gpg_home = env.get("gpghome")
    if not gpg_home:
        print "No gpghome was provided!"
        return 1
    else:
        gpg_home = gpg_home[0]

    if subprocess.call(["which", "s3cmd"]):
        print "No s3cmd found!\nInstall from http://s3tools.org/download"
        return 1

    env.Execute(Mkdir(tmp_dir))
    env.Execute(Mkdir(target_dir))

    if subprocess.call(["cp", "-r", gpg_home, tmp_dir]):
        print "Cannot copy %s to %s" % (gpg_home, tmp_dir)
        return 1
    else:
        gpg_home = os.path.join(
            remote_project_root,
            tmp_dir,
            os.path.basename(gpg_home)
            )

    virts = env.get("virts")
    ret_code = 0

    if virts is None or [v for v in virts if v.find("ubuntu") != -1]:
        ret_code += _create_deb_package(_DEB_BUILD_VM, gpg_home)

    if virts is None or [v for v in virts if v.find("centos") != -1]:
        ret_code += _create_rpm_package(_RPM_BUILD_VM, gpg_home)

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
    remote_test_command.extend(
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
    virts = env.get("virts")
    if not virts:
        virts =  _get_minimal_virt_names()
    start_cmd = ["vagrant", "up"]
    start_cmd.extend(virts)
    return subprocess.call(start_cmd)


def destroy_virtual_boxes(target, source, env):
    virts = env.get("virts")
    force = env.get("force")
    if force:
        force = force.lower() in ['true', 'yes', 'y', '1']
    if not virts:
        virts = _get_minimal_virt_names()
    destroy_cmd = ["vagrant", "destroy"]
    if not force:
        msg = "You must manually confirm deletion of VMs."
        h_border = "-" * len(msg)
        print h_border
        print msg
        print h_border
    else:
        destroy_cmd.append("-f")
    destroy_cmd.extend(virts)
    return subprocess.call(destroy_cmd)


def _create_deb_package(virt, gpg_home):
    # Assuming that all requisite packages are available on virt.
    # (see build-linux/howto.txt)
    make_file = os.path.join(tmp_dir, "make_deb")
    _create_text_file(make_file, [
        'set -e',
        'sudo apt-get update -qq',
        'sudo apt-get install -y -q ruby ruby-dev libopenssl-ruby rubygems',
        'sudo gem install -q fpm',
        'cd %s' % os.path.join(remote_project_root, build_linux_dir),
        'sh make.sh deb %s' % gpg_home
    ])
    make_file_on_vm = os.path.join(remote_project_root, make_file)
    print "\nCreating .deb package..."
    r = _run_on_virts("sh %s" % make_file_on_vm, [virt])
    if not r:
        pkg = env.Glob(os.path.join(build_linux_target_dir, "*.deb"))[0].path
        return subprocess.call(["cp", pkg, target_dir])
    return r


def _create_rpm_package(virt, gpg_home):
    # Assuming that all requisite packages are available on virt.
    # (see build-linux/howto.txt)
    # Create a temporary file to cd to required directory and make rpm.
    make_file = os.path.join(tmp_dir, "make_rpm")
    _create_text_file(make_file, [
        'set -e',
        'sudo yum install -y -q rpm-build ruby-devel rubygems',
        'sudo gem install -q fpm',
        'cd %s' % os.path.join(remote_project_root, build_linux_dir),
        'sh make.sh rpm %s' % gpg_home
    ])
    make_file_on_vm = os.path.join(remote_project_root, make_file)
    print "\nCreating .rpm package..."
    r = _run_on_virts("sh %s" % make_file_on_vm, [virt])
    if not r:
        pkg = env.Glob(os.path.join(build_linux_target_dir, "*.rpm"))[0].path
        return subprocess.call(["cp", pkg, target_dir])
    return r


def _generate_remote_test_runner_file(
    source_paths,
    test_filename_matcher,
    executable=sys.executable):

    env.Execute(Mkdir(tmp_dir))
    test_runner_file = os.path.join(tmp_dir, "run_tests")

    test_files = _get_file_paths_recursive(source_paths, test_filename_matcher)
    test_files.sort()
    # these are under the remote project root dir on virtual boxes
    test_run_paths = [os.path.join(remote_project_root, t) for t in test_files]

    run_commands = ["aggr_e=0"]
    for test in test_run_paths:
        # using printf because sh's echo in ubuntu1004 does not support
        # interpreting backslash escapes.
        run_commands.append("printf '\\n=== %s\\n' " + test)
        run_commands.append(" ".join([executable, test]))
        run_commands.append("e=$?")
        run_commands.append("printf '=== Exited with %d\\n' $e")
        run_commands.append("aggr_e=$(( $aggr_e + $e ))")
    run_commands.append("exit $aggr_e")

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
    out = open(filepath, "w")
    out.write(os.linesep.join(data))
    out.close()


def _get_arg_values(key, default=None):
    values = [v for k, v in ARGLIST if k == key]
    if not values:
        values = default
    return values


def _get_minimal_virt_names(running=False):
    return [
        v.split()[0] for v in
        subprocess
        .check_output(["vagrant", "status"])
        .splitlines()
        if v.startswith("agent-minimal-") and
        (not running or v.find(" running (") >= 0)
    ]


def _run_on_virts(remote_command, virts=None):
    exit_code = 0
    if not virts:
        virts = _get_minimal_virt_names(running=True)
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
test                Runs unit tests on specific virtual machines, bringing
                    the virtual machine up if required.
                    By default, runs on all virtual machines. Specific
                    virtual machines can be provided using the `virt` option,
                    multiple times if required.
                    By default, runs all tests in `pdagenttest` recursively.
                    (Test files should be named in the format `test_*.py`.)
                    Specific unit tests can be run by providing them as
                    arguments to the `test` option, multiple times if
                    required. Both test files and test directories are
                    supported.
                    e.g.
                    scons test test=pdagenttest/test_foo.py \\
                               virt=agent-minimal-centos
test-integration    Runs integration tests on specific virtual machines,
                    bringing the virtual machine up if required.
                    By default, runs on all virtual machines. Specific
                    virtual machines can be provided using the `virt` option,
                    multiple times if required.
                    By default, runs all tests in `pdagenttestinteg`
                    recursively. (Test files should be named in the format
                    `test_*.sh`.) Specific tests can be run by providing them
                    as arguments to the `test` option, multiple times if
                    required. Both test files and test directories are
                    supported.
                    e.g.
                    scons test-integration test=pdagenttestinteg/test_foo.sh \\
                                           virt=agent-minimal-centos
test-local          Runs unit tests on the local machine.
                    Please see 'test' command for more details about using the
                    `test` option to run specific unit tests.
""")

build_linux_dir = "build-linux"
build_linux_target_dir = os.path.join(build_linux_dir, "target")
target_dir = "target"
tmp_dir = os.path.join(target_dir, "tmp")
dist_dir = "dist"
remote_project_root = os.sep + "vagrant"

unit_test_local_task = env.Command(
    "test-local",
    _get_arg_values("test", ["pdagenttest"]),
    env.Action(run_unit_tests_local, "\n--- Running unit tests locally"))

start_virts_task = env.Command(
    "start-virt",
    None,
    env.Action(start_virtual_boxes, "\n--- Starting virtual boxes"),
    virts=_get_arg_values("virt"))

destroy_virts_task = env.Command(
    "destroy-virt",
    None,
    env.Action(destroy_virtual_boxes, "\n--- Destroying virtual boxes"),
    virts=_get_arg_values("virt"),
    force=_get_arg_values("force-destroy"))  # e.g. force-destroy=true

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
    virts=_get_arg_values("virt"),
    gpghome=_get_arg_values("gpghome"))
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
env.Depends(
    dist_task,
    [destroy_virts_task, create_packages_task, integration_test_task])

# specify directories to be cleaned up for various targets
env.Clean([unit_test_task, integration_test_task], tmp_dir)
env.Clean([create_packages_task], target_dir)
env.Clean([dist_task], dist_dir)

build_task = env.Alias("build",
    [unit_test_task, create_packages_task, integration_test_task])
env.Alias("all", ["."])

# task to run if no command is specified.
if env.GetOption("clean"):
    # workaround to get 'clean' to clean everything, and
    # not just the output of the usual default target.
    env.Default(".")
else:
    env.Default(build_task)
