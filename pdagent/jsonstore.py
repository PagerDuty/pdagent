import json
import os


class JsonStore(object):
    """
    A file-based JSON store to persist JSON-based data atomically.
    """

    def __init__(self, db_name, db_dir):
        self._path = os.path.join(db_dir, db_name)
        self._backup_path = os.path.join(db_dir, "%s.bak" % db_name)

    def get(self):
        data = None
        fp = None
        try:
            fp = open(self._path, "r")
            data = json.load(fp)
        except (IOError, ValueError):
            # file could not be opened, or had bad json in it.
            pass
        finally:
            if fp:
                fp.close()
        return data

    def set(self, json_data):
        fp = None
        try:
            fp = open(self._backup_path, "w")
            json.dump(json_data, fp)
        finally:
            if fp:
                fp.flush()
                fp.close()
        if fp:
            os.rename(self._backup_path, self._path)
