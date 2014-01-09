import json
import os


class JsonStore(object):
    """
    A file-based JSON store to persist JSON-based data atomically.
    """

    def __init__(self, db_name, db_dir):
        from pdagentutil import \
            ensure_readable_directory, ensure_writable_directory
        ensure_readable_directory(db_dir)
        ensure_writable_directory(db_dir)
        self._path = os.path.join(db_dir, db_name)
        self._backup_path = os.path.join(db_dir, "%s.bak" % db_name)

    def get(self):
        fp = None
        try:
            fp = open(self._path, "r")
            return json.load(fp)
        except (IOError, ValueError):
            # file could not be opened, or had bad json in it.
            return None
        finally:
            if fp:
                fp.close()

    def set(self, json_data):
        fp = open(self._backup_path, "w")
        try:
            json.dump(json_data, fp, separators=(',', ':'))  # compact json str
        finally:
            fp.close()
        os.rename(self._backup_path, self._path)
