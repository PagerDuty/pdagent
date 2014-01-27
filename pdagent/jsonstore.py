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
        """
        Get existing data from the JSON in the db file.
        Returns None if it cannot load the data for any reason.
        This includes bad json, file does not exist or any other
        error reading the file.
        """
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
        """
        Save given data into the db file in JSON format.
        All errors are allowed through (ie not caught within).
        This can be: json error, file permission error or any
        other error writing the file.
        """
        fp = open(self._backup_path, "w")
        try:
            json.dump(
                json_data,
                fp,
                indent=4,
                separators=(',', ': '),
                sort_keys=True)
        finally:
            fp.close()
        os.rename(self._backup_path, self._path)
