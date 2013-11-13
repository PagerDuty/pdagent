
import os, sys

def runtestdir(subdir):
    entries = os.listdir(subdir)
    total = 0
    errs = 0
    for f in entries:
        if not f.endswith(".py"):
            continue
        if not f.startswith("test_"):
            continue
        test_file = os.path.join(subdir, f)
        print >> sys.stderr, "FILE:", test_file
        exit_code = os.system(sys.executable + " " + test_file)
        total += 1
        if exit_code != 0:
            errs += 1
    print >> sys.stderr, "SUMMARY: %s -> %s total / %s error (%s)" \
        % (subdir, total, errs, sys.executable)


if __name__ == "__main__":
    #
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    os.environ["PYTHONPATH"] = project_dir # XXX: trashes current PYTHONPATH
    #
    runtestdir("pdagenttest")

